import class_logger
import class_consign
import class_login
import class_presell
import base64
import random
import string

lg = class_login.Login()
lret = lg.login('15777387154','qweasd789')
Cookies = base64.b64decode(lret['cookies']).decode()
lg.isLogin(Cookies)

cs = class_consign.Consign()
addr_id = ''.join(random.sample(string.ascii_letters + string.digits, 8))
cs.add(addr_id, Cookies)
add = cs.getAddressList(Cookies)
print(add)
cs.setOnekey(Cookies,add[1]['id'])

ps = class_presell.Presell()
print(ps.getMyPresell(Cookies))
psinfo = ps.goPresellInfo(Cookies,'5369028')
print(psinfo)
print(ps.goPresell(Cookies,'5369028','https:' + psinfo['url']))
print(ps.getMyPresell(Cookies))