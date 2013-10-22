#!/usr/bin/env python
"""
XTubeDL - Download videos from XTube in python
It requires wget to download FLV files, and is able to continue partially
downloaded videos/profiles.

xtubedl.py 'http://www.xtube.com/watch.php?v=<id>'
xtubedl.py --user 'http://www.xtube.com/user_videos.php?u=<user>'
xtubedl.py --user 'http://www.xtube.com/community/profile.php?user=<user>'
"""

import requests
import sys
import re
import urllib
import string
import subprocess
import os
from argparse import ArgumentParser, RawTextHelpFormatter
import logging

title_re = re.compile(r'.*<title>(.+)</title>.*')
flashvars_re = re.compile(r'.*<param name="flashVars" value="wall_idx=.+&user_id=(.+)&sex_type=.+&video_id=(.+)&clip_id=([a-zA-Z0-9-]+)" />.*')
profile_re = re.compile(r'\<input class\="input-disabled-url" onclick\="this\.select\(\)" value="(.+)" \/\>')

find_video_url = 'http://www.xtube.com/find_video.php'
user_videos_url = 'http://www.xtube.com/user_videos.php?u=%s'
wget_command = 'wget'

class XTubeVideo(object):
    """
    A video.

    Attributes:
        title
        user_id/video_id/clip_id
        watch_url : original link to the video
        flv_url : downloadable .flv URL
    """
    def __init__(self, watch_url):
        self.watch_url = watch_url
        vg = requests.get(watch_url)
        if vg.status_code != 200:
            raise Exception('HTTP error while getting watch page: %s'%vg.status_code)

        vs = vg.content.decode('utf-8')

        title = title_re.search(vs).group(1)
        title = title[:title.find(' - XTube')]
        self.title = title

        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        clean_title = ''.join(c for c in title if c in valid_chars)
        clean_title = clean_title.strip()
        
        matches = flashvars_re.search(vs)
        if not matches:
            raise Exception('Failed to parse flash vars.')
        self.user_id = matches.group(1)
        self.video_id = matches.group(2)
        self.clip_id = matches.group(3)
        self.clean_title = clean_title or self.user_id+' - '+self.video_id

        sp = requests.post(find_video_url, data={
            'user_id': self.user_id,
            'video_id': self.video_id,
            'clip_id': self.clip_id
        })
        if sp.status_code != 200:
            raise Exception('HTTP error while getting FLV URL: %s' % sp.status_code)
        self.flv_url = urllib.parse.unquote(sp.content[10:].decode('utf-8'))

def find_watch_urls(index_url):
    pg = requests.get(index_url)
    ps = pg.content.decode('utf-8')
    
    urls = []
    for v in profile_re.finditer(ps):
        urls.append(v.group(1))
    return urls

if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    parser.add_argument('url', help='Video URL, profile URL with --user')
    parser.add_argument('-v', '--verbose', action='count',
        help='Increase verbosity')
    parser.add_argument('-u', '--user', action='store_true',
        help='Get every videos from username or profile URL', default=False)
    parser.add_argument('-o', '--output', action='store',
        help='Output file name. Use title if empty or ends with a /')

    options = vars(parser.parse_args())

    log_level = logging.WARNING
    if options['verbose'] != None:
        verbose = int(options['verbose'])
        if verbose == 1:
            log_level = logging.INFO
        elif verbose >= 2:
            log_level = logging.DEBUG
    logging.basicConfig(level=log_level)
    
    def handle_vid(url, output):
        try:
            v = XTubeVideo(url)
            logging.debug('Video: "%s" %s/%s/%s', v.title, v.user_id, v.video_id, v.clip_id)
            logging.info('-> %s' %v.flv_url)
            output = output or './'
            if output.endswith('/'):
                if not os.path.exists(output):
                    os.makedirs(output)
                path = output + v.clean_title + '.flv'
            else:
                path = output
            subprocess.call([wget_command, v.flv_url, '-c', '-O', path])
        except Exception as e:
            logging.critical('Failed to download "%s": %s' % (url, str(e.args)))
    
    if options['user']:
        input = options['url']
        user_videos = re.match(r'^http://www\.xtube\.com/user_videos\.php\?u=(.+)', input)
        com_profile = re.match(r'^http://www\.xtube\.com/community/profile\.php\?user=(.+)', input)
        if user_videos:
            user = user_videos.group(1)
        elif com_profile:
            user = com_profile.group(1)
        else:
            user = input
            
        urls = find_watch_urls(user_videos_url % user)
        for url in urls:
            handle_vid(url, options['output'])
    else:
        handle_vid(options['url'], options['output'])


