#!/bin/env python
# coding:utf-8

import class_logger
import class_config
import class_MongoDB
from gevent import monkey
import gevent
import queue
import time
import requests
import json
import random
import hashlib
from lxml import etree
import rk
import string
import base64

monkey.patch_socket()

Min_alive = 10
Check_delay = 20 * 60
rk_username = "若快账号"
rk_pwd = "若快密码"
session_timeout = 5
max_retries = 5

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.95 Safari/537.36',
    'ContentType': 'text/html; charset=utf-8',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8',
    'Connection': 'keep-alive',
}

#代理池类
class ProxyPool():
    ProxyPool = queue.Queue(maxsize=100)
    def __init__(self):
        self.logger = class_logger.getLogger('ProxyPool')

    def getProxy(self):
        while self.ProxyPool.empty():
            gevent.sleep(1)
            self.logger.info('Proxypool is Empty')
        proxy = self.ProxyPool.get()
        if proxy['expire_time'] < time.time() + Min_alive:
            self.logger.info('Proxy is Close to Expire')
            return self.getProxy()
        proxy = "%s:%s" % (proxy['ip'], str(proxy['port']))
        proxy = {"http": "http://" + proxy, "https": "http://" + proxy}
        return proxy

    def refreshpool(self):
        url = 'http://http-webapi.zhimaruanjian.com/getip?num=100&type=2&pro=&city=0&yys=0&port=11&time=1&ts=1&ys=0&cs=1&lb=1&sb=0&pb=4&mr=1'
        while 1:
            html = requests.get(url).text
            for proxy in json.loads(html)['data']:
                timeArray = time.strptime(proxy['expire_time'], "%Y-%m-%d %H:%M:%S")
                timeStamp = int(time.mktime(timeArray))
                proxy['expire_time'] = timeStamp
                show = 0
                while self.ProxyPool.full():
                    gevent.sleep(1)
                    if show == 0:
                        self.logger.info('Unable to insert Proxy, ProxyPool is full')
                    show = 1
                if proxy['expire_time'] < time.time() + Min_alive:
                    self.logger.info('Proxy is Close to Expire')
                self.ProxyPool.put(proxy)
                self.logger.info('Put Proxy -> ' + str(proxy))

class UserPool():
    GeventPool = []
    Pool_Queue = queue.Queue(maxsize=200)
    def __init__(self, Ppool):
        self.logger = class_logger.getLogger('UserPool')
        self.Proxypool = Ppool
        self.rkclient = rk.RClient(rk_username, rk_pwd)
        self.logger.info('Initing System')
        self.dbc = class_MongoDB.MongoClient(class_config.Mongo_uri,class_logger.getLogger('MongoDB_Users'),'JD')
        self.dbc.setUnique('Users','username')

    def checkUsers(self):
        while 1:
            show = 0
            while self.Pool_Queue.empty():
                gevent.sleep(1)
                if show == 0:
                    self.logger.info('UsersPool is Empty')
                    show = 1
            work = self.Pool_Queue.get()
            #Login
            if work['last_refresh'] == 0:
                s = requests.session()
                s.timeout = session_timeout
                m = hashlib.md5()
                username = work['username']
                password = work['password']
                s.proxies = self.Proxypool.getProxy()
                self.logger.info('开始登录 -> %s:%s Proxy:%s' % (username, password,str(s.proxies)))

                r = 0
                html = ''
                while r < max_retries:
                    try:
                        html = s.get('https://passport.jd.com/new/login.aspx', headers=headers).text
                        break
                    except:
                        self.logger.warn('Proxies Error,retry:' + str(r))
                        s.proxies = self.Proxypool.getProxy()
                        r += 1

                # uuid
                property_list_reg = '//*[@id="uuid"]'
                try:
                    tree = etree.HTML(html)
                    property_lst = tree.xpath(property_list_reg)
                except:
                    self.logger.warn("Etree Error")
                    property_lst = ''

                if len(property_lst) >= 1:
                    uuid = property_lst[0].attrib['value']

                _t = 0
                cs = s.cookies.get_dict()
                for tt in cs.keys():
                    if tt != 'qr_t' and tt != 'alc':
                        _t = tt
                        # print(_t)

                imgcode = 'null'
                url = 'https://passport.jd.com/uc/showAuthCode?r=' + str(random.random()) + '&version=2015'
                r = 0
                html = ''
                while r < max_retries:
                    try:
                        html = s.get(url, headers=headers)
                        break
                    except:
                        self.logger.warn('Proxies Error,retry:' + str(r))
                        s.proxies = self.Proxypool.getProxy()
                        r += 1

                if 'false' in html:
                    self.logger.info('无需验证码')
                else:
                    # 获取验证码
                    self.logger.info("正在获取验证码")
                    url = 'https://authcode.jd.com/verify/image?a=1&acid=' + uuid + '&uid=' + uuid + '&yys=' + str(
                        int(time.time() * 1000))
                    # print(url)
                    c = ''
                    for k in s.cookies:
                        c = c + k.name + '=' + k.value + ';'
                    # print(c)
                    h = headers
                    h['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
                    h['Referer'] = 'https://passport.jd.com/uc/login?ltype=logout'
                    h['Cache-Control'] = 'no-cache'
                    h['Accept-Encoding'] = 'gzip, deflate, br'
                    h['Accept-Language'] = 'zh-CN,zh;q=0.8'

                    url = 'https://passport.jd.com/uc/showAuthCode?r=' + str(random.random()) + '&version=2015'
                    r = 0
                    img = {'content':''}
                    while r < max_retries:
                        try:
                            img = s.get(url, headers=h)
                            break
                        except:
                            self.logger.warn('Proxies Error,retry:' + str(r))
                            s.proxies = self.Proxypool.getProxy()
                            r += 1

                    im = img.content

                    self.logger.info('开始识别验证码...')
                    r = 0
                    while r < max_retries:
                        try:
                            imgcode = self.rkclient.rk_create(im, 3040)['Result']
                            break
                        except:
                            r+=1
                    self.logger.info('验证码识别完毕->' + imgcode)

                eid = ''.join(random.sample(string.ascii_letters, 10)).upper()
                eid = eid.join(random.sample(string.ascii_letters, 9)).upper() + '1'
                work['eid'] = eid
                m.update(str(int(time.time() * 1000)).encode())
                fp = m.hexdigest()
                work['fp'] = fp
                data = {
                    'uuid': uuid,
                    'eid': eid,
                    'fp': fp,
                    '_t': _t,
                    'loginType': 'c',
                    'loginname': username,
                    'nloginpwd': password,
                    'chkRememberMe': '',
                    'authcode': imgcode
                }
                # data = "uuid=%s&eid=%s&fp=%s&_t=%s&loginType=c&loginname=%s&nloginpwd=%s&chkRememberMe=&authcode=%s"%(uuid,eid,fp,_t,username,password,imgcode)
                # print(data)
                url = 'https://passport.jd.com/uc/loginService?uuid=' + uuid + '&r=' + str(
                    random.random()) + '&version=2015'
                r = 0
                while r < max_retries:
                    try:
                        h = s.post(url, data)
                        break
                    except:
                        self.logger.warn('Proxies Error,retry:' + str(r))
                        s.proxies = self.Proxypool.getProxy()
                        r += 1
                if 'success' in h.text:
                    c = ''
                    for k in s.cookies:
                        c = c + k.name + '=' + k.value + ';'
                    ret = {'state': 200,
                           'msg': '登陆成功',
                           'cookies': c}
                    work['last_refresh'] = time.time()
                    work['cookies'] = base64.b64encode(c.encode())
                    self.dbc.update('Users',{'username':work['username']},work)
                    #print(work)
                    self.logger.info('登陆成功')
                else:
                    ret = {'state': 201,
                           'msg': '登陆失败',
                           'cookies': 'null'}
                    work['alive'] = 0
                    self.dbc.update('Users', {'username': work['username']}, work)
                    self.logger.warn('登录失败')
            else:
                self.logger.info('检测存活->'+work['username'])
                url = 'https://passport.jd.com/loginservice.aspx?method=Login&callback=jQuery5411098&_=' + str(time.time() * 1000)
                #url = "http://spider.zhxwd.cn:6677/plugins/zhihu?method=showexec"
                h = headers
                h['Referer'] = 'https://item.jd.com/4229608.html'
                h['Accept'] = '*/*'
                #print(str(work['cookies']))
                h['Cookie'] = str(base64.b64decode(work['cookies']).decode())
                # proxies=self.Proxypool.getProxy()
                r = 0
                while r < max_retries:
                    try:
                        html = requests.get(url, headers=h, proxies=self.Proxypool.getProxy()).text
                        break
                    except:
                        r+=1
                        html = ''
                #print(requests.get(url, headers=h).text)
                if '"IsAuthenticated":true' in html:
                    self.logger.info('账号在线')
                    self.dbc.update('Users',{'username':work['username']},{'last_refresh':time.time()})
                else:
                    self.logger.info('账号离线,重新登录')
                    self.dbc.update('Users', {'username': work['username']}, {'last_refresh': 0})


            gevent.sleep(1)

    def refreshpool(self):
        while 1:
            project = self.dbc.get_one('Users',{'alive':1,'last_pool':{'$lt':time.time() - Check_delay},'last_refresh':{'$lt':time.time() - Check_delay}})
            if project != None:
                show = 0
                while self.Pool_Queue.full():
                    gevent.sleep(1)
                    if show == 0:
                        self.logger.warn('Unable to Put Project, pool is full')
                        show = 1
                lp = time.time()
                project['last_pool'] = lp
                self.dbc.update('Users',{'username':project['username']},{'last_pool':lp})
                #print("Update" + project['username'])
                self.Pool_Queue.put(project)
            else:
                self.logger.info('Got No Result from Server')
                gevent.sleep(1)

    def insertUsers(self,Ulist):
        for i in Ulist.keys():
            i = {
                "username":i,
                "password":UserList[i],
                "cookies":"",
                "last_refresh":0,
                "last_pool":0,
                "orders":{},
                "created_time":time.time(),
                "alive":1
            }
            if self.dbc.isexisted('Users',{"username":i['username']}) == True:
                self.logger.info('Unable to insert User, User existed')
            else:
                while self.Pool_Queue.full():
                    gevent.sleep(1)
                    self.logger.log('Unable to insert User, UserPool is full')
                self.dbc.insert_one('Users', i)

if __name__ == '__main__':
    UserList = {
    }

    class_logger.init()

    Ppool = ProxyPool()
    Upool = UserPool(Ppool)

    Main_gevent = []
    Main_gevent.append(gevent.spawn(Ppool.refreshpool))
    Main_gevent.append(gevent.spawn(Upool.refreshpool))
    Main_gevent.append(gevent.spawn(Upool.insertUsers, UserList))
    for i in range(0,10):
        Main_gevent.append(gevent.spawn(Upool.checkUsers))

    gevent.joinall(Main_gevent)