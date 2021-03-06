import json
import logging

from lxml import etree
from pkg_resources import resource_string, resource_listdir

from django.http import Http404

from xmodule.x_module import XModule
from xmodule.raw_module import RawDescriptor
from xmodule.contentstore.content import StaticContent
from xblock.core import Integer, Scope, String

import datetime
import time

log = logging.getLogger(__name__)


class VideoFields(object):
    data = String(help="XML data for the problem", scope=Scope.content)
    position = Integer(
        help="Current position in the video", scope=Scope.user_state, default=0)


class VideoModule(VideoFields, XModule):
    video_time = 0
    icon_class = 'video'

    js = {'coffee':
          [resource_string(__name__, 'js/src/time.coffee'),
           resource_string(__name__, 'js/src/video/display.coffee')] +
          [resource_string(__name__, 'js/src/video/display/' + filename)
           for filename
           in sorted(resource_listdir(__name__, 'js/src/video/display'))
           if filename.endswith('.coffee')]}
    css = {'scss': [resource_string(__name__, 'css/video/display.scss')]}
    js_module_name = "Video"

    def __init__(self, *args, **kwargs):
        XModule.__init__(self, *args, **kwargs)

        xmltree = etree.fromstring(self.data)
        self.youtube = xmltree.get('youtube')
        self.show_captions = xmltree.get('show_captions', 'true')
        self.source = self._get_source(xmltree)
        self.track = self._get_track(xmltree)
        self.start_time, self.end_time = self._get_timeframe(xmltree)

    def _get_source(self, xmltree):
        # find the first valid source
        return self._get_first_external(xmltree, 'source')

    def _get_track(self, xmltree):
        # find the first valid track
        return self._get_first_external(xmltree, 'track')

    def _get_first_external(self, xmltree, tag):
        """
        Will return the first valid element
        of the given tag.
        'valid' means has a non-empty 'src' attribute
        """
        result = None
        for element in xmltree.findall(tag):
            src = element.get('src')
            if src:
                result = src
                break
        return result

    def _get_timeframe(self, xmltree):
        """ Converts 'from' and 'to' parameters in video tag to seconds.
        If there are no parameters, returns empty string. """

        def parse_time(s):
            """Converts s in '12:34:45' format to seconds. If s is
            None, returns empty string"""
            if s is None:
                return ''
            else:
                x = time.strptime(s, '%H:%M:%S')
                return datetime.timedelta(hours=x.tm_hour,
                                          minutes=x.tm_min,
                                          seconds=x.tm_sec).total_seconds()

        return parse_time(xmltree.get('from')), parse_time(xmltree.get('to'))

    def handle_ajax(self, dispatch, get):
        '''
        Handle ajax calls to this video.
        TODO (vshnayder): This is not being called right now, so the position
        is not being saved.
        '''
        log.debug(u"GET {0}".format(get))
        log.debug(u"DISPATCH {0}".format(dispatch))
        if dispatch == 'goto_position':
            self.position = int(float(get['position']))
            log.info(u"NEW POSITION {0}".format(self.position))
            return json.dumps({'success': True})
        raise Http404()

    def get_progress(self):
        ''' TODO (vshnayder): Get and save duration of youtube video, then return
        fraction watched.
        (Be careful to notice when video link changes and update)

        For now, we have no way of knowing if the video has even been watched, so
        just return None.
        '''
        return None

    def get_instance_state(self):
        # log.debug(u"STATE POSITION {0}".format(self.position))
        return json.dumps({'position': self.position})

    def video_list(self):
        return self.youtube

    def get_html(self):
        # We normally let JS parse this, but in the case that we need a hacked
        # out <object> player because YouTube has broken their <iframe> API for
        # the third time in a year, we need to extract it server side.
        normal_speed_video_id = None  # The 1.0 speed video

        # video_list() example:
        #   "0.75:nugHYNiD3fI,1.0:7m8pab1MfYY,1.25:3CxdPGXShq8,1.50:F-D7bOFCnXA"
        for video_id_str in self.video_list().split(","):
            if video_id_str.startswith("1.0:"):
                normal_speed_video_id = video_id_str.split(":")[1]

        return self.system.render_template('video.html', {
            'streams': self.video_list(),
            'id': self.location.html_id(),
            'position': self.position,
            'source': self.source,
            'track': self.track,
            'display_name': self.display_name_with_default,
            'caption_asset_path': "/static/subs/",
            'show_captions': self.show_captions,
            'start': self.start_time,
            'end': self.end_time,
            'normal_speed_video_id': normal_speed_video_id
        })


class VideoDescriptor(VideoFields, RawDescriptor):
    module_class = VideoModule
    stores_state = True
    template_dir_name = "video"
