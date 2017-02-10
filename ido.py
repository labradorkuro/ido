#coding: utf-8
#井戸水位計測システムセンサー側プログラム

import RPi.GPIO as GPIO #GPIOライブラリをインポート
import time
import os,socket
import struct
from time import sleep
import urllib,urllib2
import fcntl
import struct
import datetime
import json
import threading
import serial
import subprocess
import numpy as np
import wiringpi #温湿度用ライブラリをインポート

spi_clk  = 11
spi_mosi = 10
spi_miso = 9
spi_ss   = 8
LED_PIN = 12
OPERATE_PIN = 22    # 稼働状況
GPIO.setwarnings(False)
#ピン番号の割り当て方式をBCMに設定
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN,GPIO.OUT,initial=GPIO.LOW)
GPIO.setup(OPERATE_PIN,GPIO.IN)

GPIO.setup(spi_mosi, GPIO.OUT)
GPIO.setup(spi_miso, GPIO.IN)
GPIO.setup(spi_clk,  GPIO.OUT)
GPIO.setup(spi_ss,   GPIO.OUT)

#温湿度用初期化
wiringpi.wiringPiSetup()
i2c = wiringpi.I2C()
dev = i2c.setup(0x40)
i2c.writeReg16(dev,0x02,0x10) #Temp + Hidi 32-bit transfer mode, LSB-MSB inverted, why?

INTERVAL = 10	#送信インターバル初期値 単位 sec
SLEEPTIME = 5 #永久ループのスリープ時間 単位 sec
TEST_INT = 1   #(テスト用)インターバルを10:1/10[60s] 20:1/20[30s] 30:1/30[20s] 60:1/60[10s]


#グローバル変数
g_macAddr = 0			#MACアドレス保存用
g_counter = 0			#単に起動してからの計測回数print用
g_sendInterval = 60 		#送信インターバル(秒)
g_cmpTime = 0			#時間経過比較用時刻

g_operate = 0           # 稼働状況
g_temp = 0.0            # 温度
g_hudi = 0.0            # 湿度

# 水位値
suii = np.array([0,0,0,0,0,0,0,0])

#url = 'http://192.168.100.7:3000/sensor_post'
url =  'https://nagaoka-satellite.com/awms/ajaxlib.php'

rlock = threading.RLock()
#
# MACアドレスの取得
#  IN: インターフェース名 ex)"eht0" "wlan0"
#
def getMacAddr(ifname):

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]


#
# 現在日時取得
#  OUT: 2016-10-21 18:34:46
#
def getDatetime():

    datet = datetime.datetime.today()     #現在日付・時刻のdatetime型データの変数を取得
    return datet.strftime("%Y-%m-%d %H:%M:%S")
#
# 稼働状況確認
#
def check_operate():
    op = 0
    if (GPIO.input(OPERATE_PIN)):
        op = 1
    print "稼働状況: %d" % op
    return op

#
# 温湿度計測
#  OUT: g_temp3=温度 g_hudi3=湿度
#
def measureTemp():

    rlock.acquire()
    global g_temp
    global g_hudi
    #LSB-MSB inverted, again...
    i2c.writeReg8(dev,0x00,0x00)  #start conversion.
    sleep((6350.0 + 6500.0 + 500.0)/1000000.0) #wait for conversion.
    temp = ((struct.unpack('4B', os.read(dev,4)))[0] << 8 | (struct.unpack('4B', os.read(dev,4)))[1])
    hudi = ((struct.unpack('4B', os.read(dev,4)))[2] << 8 | (struct.unpack('4B', os.read(dev,4)))[3])
    temp2 = ( temp / 65535.0) * 165 - 40
    hudi2 = ( hudi / 65535.0 ) * 100
    print "温度: %.2f ℃" % temp2 + "　湿度: %.2f %%" % hudi2
    g_temp = "%.2f" % temp2
    g_hudi = "%.2f" % hudi2
    rlock.release()

#
# 水位計測
#
def suii_measure():
    global suii
    global spi_clk
    global spi_mosi
    global spi_miso
    global spi_ss

    for ch in range(4):
        h = 0;
        GPIO.output(spi_ss,   False)
        GPIO.output(spi_clk,  False)
        GPIO.output(spi_mosi, False)
        GPIO.output(spi_clk,  True)
        GPIO.output(spi_clk,  False)

        cmd = (ch | 0x18) << 3
        for i in range(5):
            if (cmd & 0x80):
                GPIO.output(spi_mosi, True)
            else:
                GPIO.output(spi_mosi, False)
            cmd <<= 1
            GPIO.output(spi_clk, True)
            GPIO.output(spi_clk, False)
        GPIO.output(spi_clk, True)
        GPIO.output(spi_clk, False)
        GPIO.output(spi_clk, True)
        GPIO.output(spi_clk, False)

        value = 0
        for i in range(12):
            value <<= 1
            GPIO.output(spi_clk, True)
            if (GPIO.input(spi_miso)):
                value |= 0x1
            GPIO.output(spi_clk, False)

        GPIO.output(spi_ss, True)
        suii[ch] = value
    print "%.2f" % suii[0] + " %.2f" % suii[1] + " %.2f" % suii[2] + " %.2f" % suii[3]


def main():
    global g_macAddr
    global g_sendInterval
    global g_cmpTime
    global suii
    global g_operate
    global g_temp
    global g_hudi
    global LED_PIN

    g_cmpTime = time.time()

    #g_macAddr = getMacAddr("wlan0")
    #print g_macAddr
    firstboot = 1
    GPIO.output(LED_PIN,GPIO.HIGH)
    time.sleep(5)
    GPIO.output(LED_PIN,GPIO.LOW)
    #無限ループ
    while True:
        time.sleep(SLEEPTIME)
        # 水位計測
        suii_measure()
        # 稼働状況取得
        g_operate = check_operate()
        # 温度、湿度計測
        measureTemp()
        #10秒毎に温度湿度を計測して送信する
        if g_cmpTime+g_sendInterval < time.time():
            g_cmpTime = time.time()
            #HTTP送信
            # 小数点以下2桁のmm単位データとして送る
            params = urllib.urlencode({'func':"regRecord", 'a': g_operate,'b':suii[0],'c':g_temp, 'd':g_hudi})
            try:
                res = urllib2.urlopen(url, params)
                print "SEND DATA:%s" % params
                g_cmpTime = time.time()
                print '-----------------Alpha01-01'
                res_data =res.read()
                print res_data,     #,で改行されない
                json_res = json.loads(res_data)
                print "status=%s" % json_res['status'] + " int=%s" % json_res['int']
                if json_res['int'] > 0:
                    g_sendInterval = (json_res['int']/1000)/TEST_INT  #msec ⇒ sec
                print '\r'
                if json_res['status'] == 'OK':
       	            GPIO.output(LED_PIN,GPIO.HIGH)
                else: 
       	            GPIO.output(LED_PIN,GPIO.LOW)
            except urllib2.URLError, e:
       	        GPIO.output(LED_PIN,GPIO.LOW)
                g_sendInterval = 60          #返り値のintervalが来ないので60秒としておく
                print e
            firstboot = 0

    #GPIOを開放
    print "GPIOを開放"
    GPIO.cleanup()


if __name__ == '__main__':
  main()
