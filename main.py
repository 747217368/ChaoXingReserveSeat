
import json
import time
import argparse
import os
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


from utils import reserve, get_user_credentials
get_current_time = lambda action: time.strftime("%H:%M:%S", time.localtime(time.time() + 8*3600)) if action else time.strftime("%H:%M:%S", time.localtime(time.time()))
get_current_dayofweek = lambda action: time.strftime("%A", time.localtime(time.time() + 8*3600)) if action else time.strftime("%A", time.localtime(time.time()))


SLEEPTIME = 0.2 # 每次抢座的间隔
ENDTIME = "23:01:00" # 根据学校的预约座位时间+1min即可
ENABLE_SLIDER = False # 是否有滑块验证
MAX_ATTEMPT = 5 # 最大尝试次数
RESERVE_NEXT_DAY = True # 预约明天而不是今天的

import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import reserve, get_user_credentials

def get_current_time(action):
    return time.strftime("%H:%M:%S", time.localtime(time.time() + 8*3600)) if action else time.strftime("%H:%M:%S", time.localtime(time.time()))

def get_current_dayofweek(action):
    return time.strftime("%A", time.localtime(time.time() + 8*3600)) if action else time.strftime("%A", time.localtime(time.time()))

def split_time_range(start_time, end_time, max_duration_hours=6):
    """
    将时间范围分割成最大时长为max_duration_hours的块
    :param start_time: 开始时间，格式为"%H:%M"
    :param end_time: 结束时间，格式为"%H:%M"
    :param max_duration_hours: 每个时间块的最大时长，默认为6小时
    :return: 包含时间块的列表，每个时间块为(开始时间, 结束时间)的元组
    """
    time_format = "%H:%M"
    start_dt = datetime.strptime(start_time, time_format)
    end_dt = datetime.strptime(end_time, time_format)
    segments = []

    while start_dt < end_dt:
        chunk_end = start_dt + timedelta(hours=max_duration_hours)
        if chunk_end > end_dt:
            chunk_end = end_dt
        segments.append((start_dt.strftime(time_format), chunk_end.strftime(time_format)))
        start_dt = chunk_end

    return segments

def get_next_seat_id(seat_id):
    """
    生成下一个座位ID。根据你的座位编号方案实现此功能。
    :param seat_id: 当前座位ID，可以是单个ID或ID列表
    :return: 下一个座位ID，如果没有更多座位则返回None
    """
    if isinstance(seat_id, list):
        # 如果seat_id是列表，移动到下一个可用座位
        for id in seat_id:
            # 假设座位ID是数字或遵循某种模式
            try:
                next_seat = str(int(id) + 1)
                return next_seat
            except ValueError:
                continue
    return None

def login_and_reserve(users, usernames, passwords, action, success_list=None):
    """
    登录并预订座位
    :param users: 用户信息列表，每个用户包含username, password, times, roomid, seatid, daysofweek
    :param usernames: 用户名列表，用逗号分隔
    :param passwords: 密码列表，用逗号分隔
    :param action: 操作标识
    :param success_list: 成功预订的列表，默认为None
    :return: 成功预订的列表
    """
    logging.info(f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}")
    if action and len(usernames.split(",")) != len(users):
        raise Exception("用户数量应与配置数量匹配")
    if success_list is None:
        success_list = [False] * len(users)
    current_dayofweek = get_current_dayofweek(action)
    
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        if action:
            username, password = usernames.split(',')[index], passwords.split(',')[index]
        if(current_dayofweek not in daysofweek):
            logging.info("今天未设置预订")
            continue
        
        # 如果总时长超过6小时，将时间段分割成多个段
        start_time, end_time = times
        segments = split_time_range(start_time, end_time)
        
        for segment_start, segment_end in segments:
            while seatid:
                logging.info(f"----------- {username} -- {segment_start} to {segment_end} -- {seatid} try -----------")
                s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
                s.get_login_status()
                s.login(username, password)
                s.requests.headers.update({'Host': 'office.chaoxing.com'})
                suc = s.submit([segment_start, segment_end], roomid, seatid, action)
                if suc:
                    # 成功预订此时间段
                    success_list[index] = True
                    logging.info(f"成功为{username}预订从{segment_start}到{segment_end}的时间段。")
                    break
                else:
                    # 如果当前座位被占用，获取下一个座位ID并立即重试
                    seatid = get_next_seat_id(seatid)
                    if seatid is None:
                        logging.info(f"对于{username}从{segment_start}到{segment_end}的时间段，没有更多座位可用。")
                        break
            else:
                logging.info(f"对于{username}从{segment_start}到{segment_end}的时间段，尝试了所有座位但无一可用。")
    return success_list

def main(users, action=False):
    current_time = get_current_time(action)
    logging.info(f"start time {current_time}, action {'on' if action else 'off'}")
    attempt_times = 0
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
    success_list = [False] * len(users)
    current_dayofweek = get_current_dayofweek(action)
    today_reservation_num = sum(1 for d in users if current_dayofweek in d.get('daysofweek'))
    
    while current_time < ENDTIME:
        attempt_times += 1
        success_list = login_and_reserve(users, usernames, passwords, action, success_list)
        print(f"attempt time {attempt_times}, time now {current_time}, success list {success_list}")
        current_time = get_current_time(action)
        if sum(success_list) == today_reservation_num:
            print(f"Reserved successfully!")
            break  # Ensure to stop if all required reservations are successful.


def debug(users, action=False):
    logging.info(f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}")
    suc = False
    logging.info(f" Debug Mode start! , action {'on' if action else 'off'}")
    if action:
        usernames, passwords = get_user_credentials(action)
    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        if type(seatid) == str:
            seatid = [seatid]
        if action:
            username ,password = usernames.split(',')[index], passwords.split(',')[index]
        if(current_dayofweek not in daysofweek):
            logging.info("Today not set to reserve")
            continue
        logging.info(f"----------- {username} -- {times} -- {seatid} try -----------")
        s = reserve(sleep_time=SLEEPTIME,  max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER)
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({'Host': 'office.chaoxing.com'})
        suc = s.submit(times, roomid, seatid, action)
        if suc:
            return

def get_roomid(args1, args2):
    username = input("请输入用户名：")
    password = input("请输入密码：")
    s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
    s.get_login_status()
    s.login(username=username, password=password)
    s.requests.headers.update({'Host': 'office.chaoxing.com'})
    encode = input("请输入deptldEnc：")
    s.roomid(encode)

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    parser = argparse.ArgumentParser(prog='Chao Xing seat auto reserve')
    parser.add_argument('-u','--user', default=config_path, help='user config file')
    parser.add_argument('-m','--method', default="reserve" ,choices=["reserve", "debug", "room"], help='for debug')
    parser.add_argument('-a','--action', action="store_true",help='use --action to enable in github action')
    args = parser.parse_args()
    func_dict = {"reserve": main, "debug":debug, "room": get_roomid}
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)