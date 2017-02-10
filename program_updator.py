#coding: utf-8
#消雪装置データ管理システム通信端末プログラムダウンロード＆リブート (Alpha01)

import os
import urllib,urllib2
import time
from time import sleep
import shutil
import filecmp
import datetime

SLEEPTIME = 0.1 #永久ループのスリープ時間 単位 sec

#グローバル変数
g_interval = 60 * 10       #現在は10分間隔 (送信インターバル(秒) 60(1分)x60(1時間)x24(1日))
#g_interval = 30
g_cmpTime = 0			   #時間経過比較用時刻


# url = 'http://192.168.100.12:3000/upload/shousetsu.py'
url = 'https://nagaoka-satellite.com/awms/upload/ido.py'
org_file = "/home/pi/ido.py"
dl_file = "/home/pi/nsl_dl/ido.py"
dl_path = "/home/pi/nsl_dl"

def getDatetime():

    datet = datetime.datetime.today()     #現在日付・時刻のdatetime型データの変数を取得
    return datet.strftime("%Y-%m-%d %H:%M:%S")

def main():

    global g_interval
    global g_cmpTime

    if (os.path.isdir(dl_path) == False):
        os.mkdir(dl_path)
    g_cmpTime = time.time()

    #無限ループ
    while True:
        time.sleep(SLEEPTIME)
        #g_interval時間おきにtry:の処理を行う
        if( g_cmpTime+g_interval < time.time()):
            print '-----------------Alpha01-01 ' + getDatetime()
            try:
                #ファイルがあるかチェック(なければexcept:)
                urllib2.urlopen(url)
                #Webからファイルをダウンロードする(HTTP GET)
                urllib.urlretrieve(url,"{0}".format(dl_file))
                #ファイルが更新されているか
                cmp = filecmp.cmp(org_file, dl_file)  # 0:different
                #print(b if "あり" else "なし")
                if( cmp == False ):
                    shutil.copy(dl_file, org_file)
                    print org_file,"を更新しました"
                    os.system("sudo /sbin/reboot")
                else:
                    print org_file,"の変更はありません"
            except urllib2.URLError, e:
                print "アップロードファイルがありません"
            g_cmpTime = time.time()

if __name__ == '__main__':
  main()
