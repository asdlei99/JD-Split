import os
from rk import *
import requests
import re
import lxml.etree as etree
import time
import random
import string
import hashlib
import json
import urllib.request
import class_logger
from gevent import monkey
import gevent
monkey.patch_socket()
import queue

url = 'https://passport.jd.com/new/login.aspx'

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.95 Safari/537.36',
    'ContentType': 'text/html; charset=utf-8',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8',
    'Connection': 'keep-alive',
}

BuyNow = False
Refresh_Time = 60 * 30
pool = queue.Queue(maxsize=1000)
url = 'http://http-webapi.zhimaruanjian.com/getip?num=200&type=2&pro=&city=0&yys=0&port=11&time=1&ts=1&ys=0&cs=1&lb=1&sb=0&pb=4&mr=1'
html = requests.get(url).text
for proxyMeta in json.loads(html)['data']:
    proxyMeta = "%s:%s" % (proxyMeta['ip'], str(proxyMeta['port']))
    proxyMeta = {"http": "http://" + proxyMeta, "https": "http://" + proxyMeta}
    pool.put(proxyMeta)

class JDUser(object):
    def getProxy(self):
        # 代理服务器
        proxyMeta = pool.get()
        #print (proxyMeta)
        return proxyMeta


    def __init__(self,logger, username, password, rk_username, rk_pwd, product):
        self.s = requests.Session()
        self.s.headers = headers
        self.proxies = self.getProxy()
        self.s.proxies = self.proxies
        self.username = username
        self.password = password
        self.rkclient = RClient(rk_username, rk_pwd)
        self.product = product
        self.TrackID = ''
        self.pid = ''
        self.logger = logger
        if self.login() == True:
            self.addconsign()
            init = time.time()
            stop = 0
            while stop == 0:
                now = time.time()
                if now - init > Refresh_Time:
                    self.keepOnline()
                    init = now
                if BuyNow == True:
                    if self.oneKeybuy(product)['state'] == 201:
                        self.s.close()
                        self.s = requests.Session()
                        self.login()
                        self.oneKeybuy(product)
                    self.getHome()
                    stop = 1
                gevent.sleep(1)

    # 账号登录函数
    def login(self):
        m = hashlib.md5()
        username = self.username
        password = self.password
        self.logger.info('开始登录 -> %s:%s' % (username,password))

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
        }
        r = 0
        while r <3:
            try:
                html = self.s.get('https://passport.jd.com/new/login.aspx', headers=headers).text
                break
            except:
                self.logger.warn('Proxies Error,retry:' + str(r))
                self.proxies = self.getProxy()
                self.s.proxies = self.proxies
                r+=1

        # uuid
        property_list_reg = '//*[@id="uuid"]'
        tree = etree.HTML(html)
        property_lst = tree.xpath(property_list_reg)
        if len(property_lst) >= 1:
            uuid = property_lst[0].attrib['value']

        # _t
        '''
        property_list_reg = '//*[@id="token"]'
        tree = etree.HTML(html)
        property_lst = tree.xpath(property_list_reg)
        if len(property_lst) >= 1:
            _t = property_lst[0].attrib['value']
        '''
        cs = self.s.cookies.get_dict()
        for tt in cs.keys():
            if tt != 'qr_t' and tt != 'alc':
                _t = tt
                # print(_t)

        imgcode = 'null'
        url = 'https://passport.jd.com/uc/showAuthCode?r=' + str(random.random()) + '&version=2015'
        html = self.s.get(url, headers=headers)
        if 'false' in html:
            self.logger.info('无需验证码')
        else:
            # 获取验证码
            self.logger.info("正在获取验证码")
            url = 'https://authcode.jd.com/verify/image?a=1&acid=' + uuid + '&uid=' + uuid + '&yys=' + str(
                int(time.time() * 1000))
            # print(url)
            c = ''
            for k in self.s.cookies:
                c = c + k.name + '=' + k.value + ';'
            # print(c)
            h = headers
            h['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
            h['Referer'] = 'https://passport.jd.com/uc/login?ltype=logout'
            h['Cache-Control'] = 'no-cache'
            h['Accept-Encoding'] = 'gzip, deflate, br'
            h['Accept-Language'] = 'zh-CN,zh;q=0.8'
            img = self.s.get(url, headers=h)

            im = img.content


            self.logger.info('开始识别验证码...')
            imgcode = self.rkclient.rk_create(im, 3040)['Result']
            self.logger.info('验证码识别完毕->' + imgcode)



        eid = ''.join(random.sample(string.ascii_letters, 10)).upper()
        eid = eid.join(random.sample(string.ascii_letters, 9)).upper() + '1'
        self.eid = eid
        # print(eid)
        m.update(str(int(time.time() * 1000)).encode())
        fp = m.hexdigest()
        self.fp = fp
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
        url = 'https://passport.jd.com/uc/loginService?uuid=' + uuid + '&r=' + str(random.random()) + '&version=2015'
        r = 0
        while r <3:
            try:
                h = self.s.post(url, data)
                break
            except:
                self.logger.warn('Proxies Error,retry:' + str(r))
                self.proxies = self.getProxy()
                self.s.proxies = self.proxies
                r+=1
        if 'success' in h.text:
            c = ''
            for k in self.s.cookies:
                c = c + k.name + '=' + k.value + ';'
            ret = {'state': 200,
                   'msg': '登陆成功',
                   'cookies': c}
            self.TrackID = self.s.cookies.get('TrackID')
            self.logger.info('登陆成功')
            return True
        else:
            ret = {'state': 201,
                   'msg': '登陆失败',
                   'cookies': 'null'}
            self.logger.warn('登录失败')
            return False


        #print(json.dumps(ret))

    def addconsign(self):
        h = headers
        h['Referer'] = 'https://trade.jd.com/shopping/dynamic/consignee/editConsignee.action?isOverSea=1&t=' + str(time.time()*1000)
        h['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        data = {
            "consigneeParam.id": "",
            "consigneeParam.type": "1",
            "consigneeParam.name": "胡天",
            "consigneeParam.provinceId": "19",
            "consigneeParam.cityId": "1655",
            "consigneeParam.countyId": "4255",
            "consigneeParam.townId": "0",
            "consigneeParam.address": "虎门镇振兴大道???",
            "consigneeParam.mobile": self.username,
            "consigneeParam.email": "",
            "consigneeParam.phone": "",
            "consigneeParam.provinceName": "广东",
            "consigneeParam.cityName": "东莞市",
            "consigneeParam.countyName": "虎门",
            "consigneeParam.townName": "",
            "consigneeParam.commonConsigneeSize": "0",
            "consigneeParam.isUpdateCommonAddress": "1",
            "consigneeParam.giftSenderConsigneeName": "",
            "consigneeParam.giftSendeConsigneeMobile": "",
            "consigneeParam.noteGiftSender": "false",
            "consignee_ceshi1": "",
            "consigneeParam.idCard": "",
            "consigneeParam.addressName": "虎门镇振兴大道✘",
            "consigneeParam.areaCode": "0086",
            "consigneeParam.nameCode": "",
            "consigneeParam.zip=": ""
        }
        self.s.post('https://trade.jd.com/shopping/dynamic/consignee/saveConsignee.action', headers=h, data=data)
        self.logger.info("收货地址保存成功")

    def oneKeybuy(self,product):
        h = headers
        h['Referer'] = 'https://item.jd.com/%s.html'%product
        h['Accept'] = '*/*'
        url = 'https://easybuy.jd.com/skuDetail/newSubmitEasybuyOrder.action?callback=easybuysubmit&skuId=' + product + '&num=1&gids=&ybIds=&did=&useOtherAddr=false&_=' + str(time.time()*1000)
        act = self.s.get(url,headers = h).text
        self.logger.info(act)
        if 'EasyOrderInfo' in act:
            self.logger.info('二步操作')
            url = "https:" + re.findall(r'jumpUrl":"(.*?)"',act)[0]
            self.logger.info('Url ->' + url)
            h['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
            html = self.s.get(url, headers=h).text
            # eid
            property_list_reg = '//*[@id="eid"]'
            tree = etree.HTML(html)
            property_lst = tree.xpath(property_list_reg)
            if len(property_lst) >= 1:
                eid = property_lst[0].attrib['value']
                #print(eid)
            # TrackID
            property_list_reg = '//*[@id="TrackID"]'
            tree = etree.HTML(html)
            property_lst = tree.xpath(property_list_reg)
            if len(property_lst) >= 1:
                TrackID = property_lst[0].attrib['value']
                #print(TrackID)
            # riskControl
            property_list_reg = '//*[@id="riskControl"]'
            tree = etree.HTML(html)
            property_lst = tree.xpath(property_list_reg)
            if len(property_lst) >= 1:
                riskControl = property_lst[0].attrib['value']
                #print(riskControl)
            # fp
            property_list_reg = '//*[@id="fp"]'
            tree = etree.HTML(html)
            property_lst = tree.xpath(property_list_reg)
            if len(property_lst) >= 1:
                fp = property_lst[0].attrib['value']
                #print(fp)

            data = {
                'overseaPurchaseCookies':'',
                'submitOrderParam.sopNotPutInvoice':False,
                'submitOrderParam.trackID':TrackID,
                'ebf':1,
                'submitOrderParam.ignorePriceChange':0,
                'submitOrderParam.btSupport':0,
                'submitOrderParam.eid':eid,
                'submitOrderParam.fp':fp,
                'riskControl':riskControl
            }
            h['Referer'] = 'https://trade.jd.com/shopping/order/getEasyOrderInfo.action?rid=' + str(time.time()*1000)
            h['Accept'] = 'application/json, text/javascript, */*; q=0.01'
            res = self.s.post('https://trade.jd.com/shopping/order/submitOrder.action',data=data,headers=h)
            print(res.text)
            if '立即抢购' in res.text:
                ret = {'state':202,'msg':'这是抢购商品'}
                self.logger.info('这是抢购商品')
            elif '请修改后再提交' in res.text:
                ret = {'state': 201, 'msg': '地址需要二次处理,开始处理'}
                self.logger.info('地址需要二次处理,开始处理')
            elif '请稍后再试' in res.text:
                ret = {'state': 203, 'msg': '提交过快'}
                self.logger.info('提交过快')
            elif '收货人信息不对' in res.text:
                ret = {'state': 204, 'msg': '收货人信息错误'}
                self.logger.info('收货人信息错误')
            else:
                self.logger.info('下单成功')
                ret = {'state': 200, 'msg': '下单成功'}
        else:
            self.logger.info('下单成功')
            ret = {'state': 200, 'msg': '下单成功'}
        self.logger.info(ret)
        return ret

    def getHome(self):
        post = {}
        res = self.s.get(url = 'https://order.jd.com/center/list.action?s=1',headers = headers).text
        parse = re.findall(r"\$ORDER_CONFIG\['(orderIds|orderWareTypes|orderWareIds|orderTypes|orderSiteIds)'\]='(.*?)';",res)
        for gg in parse:
            (a,b) = gg
            post[a] = b
        html = self.s.post(url='https://order.jd.com/lazy/getOrderProductInfo.action',data=post).text
        try:
            jarr = json.loads(html)
            for i in jarr:
                self.logger.info('Products -> ' + i['name'] + ' ; Id -> ' + str(i['productId']))
        except:
            self.logger.warn('Get Products Failed')

if __name__ == '__main__':
    zh = {
		"15578350482":"qweasd789",
        "18905245463":"qweasd789",
    }

    jobs = []
    logC = class_logger
    logC.init()
    k = 0
    for i in zh:
        #print(i,zh[i])
        jd_user = i
        jd_pwd = zh[i]
        rk_user = 'lengyue233'
        rk_pwd = 'Lengyue0331'
        if k < 2:
            jobs.append(gevent.spawn(JDUser, logC.getLogger('T -> ' + i), jd_user, jd_pwd, rk_user, rk_pwd, '5001175'))
            k+=1
    try:
        
        #BuyNow = True
        while 1:
            url = 'https://p.3.cn/prices/mgets?callback=jQuery6571104&type=1&area=19_1601_3634_0.218533822&pdtk=&pduid=609339652&pdpin=&pin=null&pdbp=0&skuIds=J_3513163&ext=11000000&source=item-pc'
            price = re.findall(r'"p":"(.*?)"',requests.get(url).text)[0]
            print(price)
            if price >= "38.10":
                print("开始抢购")
                break
            gevent.sleep(1)
        gevent.joinall(jobs)
    finally:
        print('T Success')


    #a.addcart()
    #a.submit()