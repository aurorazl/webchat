from django.shortcuts import render,HttpResponse
import requests
import time
import re
import json
ctime=None
qcode = None
tip = 1
ticket_dict = {}
USER_INIT_DICT = {}
ALL_COOKIE_DICT = {}

def login(request):
    global ctime
    ctime = time.time()     #时间窗，用于生成请求url
    response = requests.get(
        url='https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb&fun=new&lang=zh_CN&_=%s' % ctime
        #r后面一般是时间窗，redirect_url=xxx完成操作后跳转url，可以删除
    )
    code = re.findall('uuid = "(.*)";',response.text)
    global qcode
    qcode = code[0]          #保存请求的url码，以后可能有用
    return render(request,'login.html',{'qcode':qcode})

def check_login(request):
    global tip          #拿到全局变量
    ret = {'code':408,'data':None}      # 或者session
    r1 = requests.get(
        url='https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?loginicon=true&uuid=%s&tip=%s&sr=-1767722401&_=%s' %(qcode,tip,ctime,)  #传请求二维码的参数
    )
    # 这时向微信请求，pending多久看微信什么时候返回
    if 'window.code=408' in r1.text:
        print('无人扫码')
        return HttpResponse(json.dumps(ret))
    elif 'window.code=201' in r1.text:      # 已扫码，返回头像url给前端，再继续监听同一个url看是否确认
        ret['code']=201
        avatar = re.findall("window.userAvatar = '(.*)';", r1.text)[0]
        ret['data']=avatar
        tip = 0     # 修改一下请求url的参数
        return HttpResponse(json.dumps(ret))
    elif 'window.code=200' in r1.text:  # 已确认
        ALL_COOKIE_DICT.update(r1.cookies.get_dict())           #更新第一次确认的cookie，可能有用
        redirect_url = re.findall('window.redirect_uri="(.*)";',r1.text)[0]     # 不同设备重定向url可能不一样
        redirect_url = redirect_url + "&fun=new&version=v2&lang=zh_CN"         # 新的重定向url添加后缀去请求用户数据
        r2 = requests.get(url=redirect_url)
        # 获取凭证
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r2.text,'html.parser')
        for tag in soup.find('error').children:     #找到所有的登陆凭证
            ticket_dict[tag.name]= tag.get_text()     #字典类型，引用类型，修改值不用global
        # print(ticket_dict)
        ALL_COOKIE_DICT.update(r2.cookies.get_dict())   #更新重定向的cookie，可能有用
        ret['code'] = 200
        return HttpResponse(json.dumps(ret))

def user(request):
    """
    个人主页
    :param request:
    :return:
    """
    #获取用户信息
    user_info_url = "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit?r=-1780597526&lang=zh_CN&pass_ticket=" + \
                    ticket_dict['pass_ticket']
    user_info_data = {
        'BaseRequest': {
            'DeviceID': "e459555225169136",  # 这个随便写，没获取过
            'Sid': ticket_dict['wxsid'],
            'Skey': ticket_dict['skey'],        # 全部在用户凭证里
            'Uin': ticket_dict['wxuin'],
        }
    }
    r3 = requests.post(
        url=user_info_url,
        json=user_info_data,  # 不能data，否则只能拿到key，value传不了
    )
    r3.encoding = 'utf-8'  # 编码
    user_init_dict = json.loads(r3.text)  # loads将text字符串类型转为字典类型
    ALL_COOKIE_DICT.update(r3.cookies.get_dict())       #再次保存cookie，这样就包含了以上所有流程的cookie
    # USER_INIT_DICT 已声明为空字典，内存地址已有，添加值不修改地址，但赋值会改变地址，比如=123，之前要声明global即可。
    # USER_INIT_DICT['123']=123,    USER_INIT_DICT.update(user_init_dict)两种做法都没改变地址
    USER_INIT_DICT.update(user_init_dict)
    print(user_init_dict)
    return render(request,'user.html',{'user_init_dict':user_init_dict})

def contact_list(request):
    """
    获取所有联系人
    :param request:
    :return:
    """
    #https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&pass_ticket=Km1HxNhHgssUN4pPiyoPLaUOb91k30uqBeTGExzKE5Ls44RUVPUhcRI8T%252Foo7hXj&r=1530815125931&seq=0&skey=@crypt_2f6a0375_d2019115cb94112608afa8e3145516d0
    base_url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&pass_ticket=%s&r=%s&seq=0&skey=%s'
    ctime = str(time.time())    #加不加str都行，本身是float类型
    url = base_url %(ticket_dict['pass_ticket'],ctime,ticket_dict['skey'])
    response = requests.get(url=url,cookies=ALL_COOKIE_DICT)                    #看url带凭证行不行，不行就带cookie，再不行就带请求头
    response.encoding='utf-8'
    contact_list_dict = json.loads(response.text)
    return render(request,'contact_list.html',{'contact_list_dict':contact_list_dict})

def sendMsg(request):
    """
    发送消息
    :param request:
    :return:
    """
    to_user = request.GET.get('toUser')
    msg = request.GET.get('msg')
    url= 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg?lang=zh_CN&pass_ticket=%s' %(ticket_dict['pass_ticket'])
    ctime = str(time.time())
    post_data = {
        'BaseRequest': {
            'DeviceID': "e459555225169136",
            'Sid': ticket_dict['wxsid'],
            'Skey': ticket_dict['skey'],
            'Uin': ticket_dict['wxuin'],
        },
        'Msg':{
            'ClientMsgId': ctime,
            'Content':msg,
            'FromUserName':USER_INIT_DICT['User']['UserName'],
            'LocalID':ctime,
            'ToUserName': to_user.strip(),      #两端可能有空格，清除
            'Type':1
        },'Scene':0
    }
    #response = requests.post(url=url,json=post_data)          #发消息要看官方要不要带请求头，要相同。json内部会携带下面的请求头
    #response = requests.post(url=url,data=json.dumps(post_data),headers={'Content-Type':'application/json;charset=utf-8'}) #两种方式写法相等
    #注：有时候带着请求头可能会发送不了消息，与sendmsg请求里相同，不带请求头即可，这时data而不是json
    #发中文，显示unicode编码，需要声明ensure_ascii=False，才能不转化中文，但会触发下面问题
    # data\json字段传的可以是字典，字符串，字节，文件对象，传的时候都会通过encode('utf-8')编码成字节。json.dumps转为字符串后，由于声明不转换中文，含中文的字符串
    # data默认用'latin-1'编码成字节，转不了中文，需要主动将中文通过utf-8转为字节
    response = requests.post(url=url, data=bytes(json.dumps(post_data,ensure_ascii=False),encoding='utf-8'))
    return HttpResponse('ok')

def getMsg(request):
    """
    获取消息
    :param request:
    :return:
    """
    # 1.登陆成功后，初始化操作时，获取到一个SyncKey，
    # 2.带着SyncKey检测是否是否有消息到来，
    # 3.如果window.synccheck={retcode:"0",selector:"2"}，有消息到来
    #   3.1.发请求获取消息，以及新的SyncKey
    #   3.2.带着新的SyncKey去检测是否有消息
    synckey_list = USER_INIT_DICT['SyncKey']['List']
    sync_list = []
    for item in synckey_list:
        temp = "%s_%s" % (item['Key'], item['Val'],)
        sync_list.append(temp)
    synckey = "|".join(sync_list)
    #base_url = 'https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck?r=%s&skey=%s&sid=%s&uin=%s&deviceid=%s&synckey=%s'
    r1 = requests.get(
        url='https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck',
        params={
            'r':time.time(),
            'skey':ticket_dict['skey'],
            'sid':ticket_dict['wxsid'],
            'uin':ticket_dict['wxuin'],
            'deviceid':'e843458050524287',
            'synckey':synckey
        },
        cookies = ALL_COOKIE_DICT           #不加cookie的话会hold不住，一直发请求，加了后就等待pending
    )
    if 'retcode:"0",selector:"2"' in r1.text:   #等待r1返回数据作判断
        post_data = {
            'BaseRequest': {
                'DeviceID': "e459555225169136",
                'Sid': ticket_dict['wxsid'],
                'Skey': ticket_dict['skey'],
                'Uin': ticket_dict['wxuin'],
            },
            'SyncKey':USER_INIT_DICT['SyncKey'],    # 不用格式化，直接传
            'rr':1  # 随便写
        }
        # 获取消息
        r2 = requests.post(
            url='https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsync',
            params = {
                'skey':ticket_dict['skey'],
                'sid':ticket_dict['wxsid'],
                'pass_ticket':ticket_dict['pass_ticket'],
                'lang':'zh_CN'
            },
            json=post_data      # 先不加cookie，不行再加
        )
        r2.encoding='utf-8'
        msg_dict=json.loads(r2.text)                                #返回的所有内容
        for msg in msg_dict['AddMsgList']:                      #AddMsgList包含所有人这个时刻发来的消息
            print(msg['Content'])                                 #如果是群聊，content还包含发送人的username，用于标记，根据它获取昵称
        USER_INIT_DICT['SyncKey'] = msg_dict['SyncKey']         #更新值
    return HttpResponse('ok')