#!/usr/bin/python

import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import configparser
sys.dont_write_bytecode = True
reload(sys)
sys.setdefaultencoding('utf8')

def non_zero_min(values):
    "Return the min value but always prefer non-zero values if they exist"
    if len(values) == 0:
        raise TypeError('non_zero_min expected 1 arguments, got 0')
    non_zero_values = [i for i in values if i != 0]
    if non_zero_values:
        return min(non_zero_values)
    return 0


class Transcoder(object):

    # path to the transcoder root foler
    TRANSCODER_ROOT = "/transcoder"
    # directory containing new video to transcode
    INPUT_DIRECTORY = TRANSCODER_ROOT + '/input'
    # directory where handbrake will save the output to. this is a temporary
    # location and the file is moved to OUTPUT_DIRECTORY after complete
    WORK_DIRECTORY = TRANSCODER_ROOT + '/work'
    # directory containing the original inputs after they've been transcoded
    COMPLETED_DIRECTORY = TRANSCODER_ROOT + '/completed-originals'
    # directory contained the compressed outputs
    OUTPUT_DIRECTORY = TRANSCODER_ROOT + '/output'
    # Configuration File
    CONFIG_FILE = '/config/conf.py'

    # number of seconds a file must remain unmodified in the INPUT_DIRECTORY
    # before it is considered done copying. increase this value for more
    # tolerance on bad network connections.
    WRITE_THRESHOLD = 30
    # path to logfile
    LOGFILE = TRANSCODER_ROOT + '/transcoder.log'

    def __init__(self):
        self.running = False
        self.logger = None
        self.current_command = None
        self._default_handlers = {}

    def setup_signal_handlers(self):
        "Setup graceful shutdown and cleanup when sent a signal"
        def handler(signum, frame):
            self.stop()

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            self._default_handlers[sig] = signal.signal(sig, handler)

    def restore_signal_handlers(self):
        "Restore the default handlers"
        for sig, handler in self._default_handlers.items():
            signal.signal(sig, handler)
        self._default_handlers = {}

    def execute(self, command):
        # TODO: use Popen and assign to current_command so we can terminate
        args = shlex.split(command)
        out = subprocess.check_output(args=args, stderr=subprocess.STDOUT)
        return out

    def setup_logging(self):
        self.logger = logging.getLogger('transcoder')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(self.LOGFILE)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info('Transcoder started and scanning for input')

    def check_filesystem(self):
        "Checks that the filesystem and logger is setup properly"
        dirs = (self.INPUT_DIRECTORY, self.WORK_DIRECTORY,
                self.OUTPUT_DIRECTORY, self.COMPLETED_DIRECTORY)
        if not all(map(os.path.exists, dirs)):
            for path in dirs:
                if not os.path.exists(path):
                    try:
                        os.mkdir(path)
                    except OSError as ex:
                        msg = 'Cannot create directory "%s": %s' % (
                            path, ex.strerror)
                        sys.stdout.write(msg)
                        sys.stdout.flush()
                        return False

        if not self.logger:
            self.setup_logging()
        return True

    def stop(self):
        # guard against multiple signals being sent before the first one
        # finishes
        if not self.running:
            return
        self.running = False
        self.logger.info('Transcoder shutting down')
        if self.current_command:
            self.current_command.terminate()
        # logging
        logging.shutdown()
        self.logger = None
        # signal handlers
        self.restore_signal_handlers()

    def run(self):
        self.running = True
        self.setup_signal_handlers()

        while self.running:
            if self.check_filesystem():
                self.check_for_input()
            time.sleep(5)

    def check_for_input(self):
        "Look in INPUT_DIRECTORY for an input file and process it"
        for filename in os.listdir(self.INPUT_DIRECTORY):
            if filename.startswith('.'):
                continue
            path = os.path.join(self.INPUT_DIRECTORY, filename)
            if (time.time() - os.stat(path).st_mtime) > self.WRITE_THRESHOLD:
                # when copying a file from windows to the VM, the filesize and
                # last modified times don't change as data is written.
                # fortunately these files seem to be locked such that
                # attempting to open the file for reading raises an IOError.
                # it seems reasonable to skip any file we can't open
                try:
                    f = open(path, 'r')
                    f.close()
                except IOError:
                    continue

                self.process_input(path)
                # move the source to the COMPLETED_DIRECTORY
                dst = os.path.join(self.COMPLETED_DIRECTORY,
                                   os.path.basename(path))
                shutil.move(path, dst)
                break

    def process_input(self, path):
        name = os.path.basename(path)
        self.logger.info('Found new input "%s"', name)

        # if any of the following functions return no output, something
        # bad happened and we can't continue

        # parse the input meta info.
        meta = self.scan_media(path)
        if not meta:
            return
        # Detect if the video is Interlaced
        interlace = self.detect_interlace(path)
        if not interlace:
            return

        # determine crop dimensions
        crop = self.detect_crop(path)
        if not crop:
            return

        # transcode the video
        work_path = self.transcode(path, crop, meta, interlace)
        if not work_path:
            return

        # move the completed output to the output directory
        self.logger.info('Moving completed work output %s to output directory',
                         os.path.basename(work_path))
        output_path = os.path.join(self.OUTPUT_DIRECTORY,
                                   os.path.basename(work_path))
        shutil.move(work_path, output_path)
        shutil.move(work_path + '.log', output_path + '.log')

    def scan_media(self, path):
        "Use handbrake to scan the media for metadata"
        name = os.path.basename(path)
        self.logger.info('Scanning "%s" for metadata', name)
        command = 'HandBrakeCLI --scan --input "%s"' % path
        try:
            out = self.execute(command)
        except subprocess.CalledProcessError as ex:
            if 'unrecognized file type' in ex.output:
                self.logger.info('Unknown media type for input "%s"', name)
            else:
                self.logger.info('Unknown error for input "%s" with error: %s',
                                 name, ex.output)
            return None

        # process out
        return out

    def detect_interlace(self, path):
        name = os.path.basename(path)
        self.logger.info('Using Media info to detect if "%s" is interlaced', name)
        command_parts = [
            'mediainfo',
            '--Inform="Video;%ScanType%"',
            '"%s"' % path
        ]
        command = ' '.join(command_parts)
        try:
            out = self.execute(command)
        except subprocess.CalledProcessError as ex:
            self.logger.info('detecting of interlaced video for "%s" has failed: error "%s"', name, ex)
            return ' '
        out = out.strip(' \t\n\r')
        if out == 'Interlaced':
            return '--filter deinterlace'
        else:
            return ' '


    def detect_crop(self, path):
        crop_re = r'[0-9]+:[0-9]+:[0-9]+:[0-9]+'
        name = os.path.basename(path)
        self.logger.info('Detecting crop for input "%s"', name)
        command = 'detect-crop --values-only "%s"' % path
        try:
            out = self.execute(command)
        except subprocess.CalledProcessError as ex:
            # when detect-crop detects discrepancies between handbrake and
            # mplayer, each crop is written out but detect-crop also returns
            # an error code. if this is the case, we don't want to error out.
            if re.findall(crop_re, ex.output):
                out = ex.output
            else:
                self.logger.info('detect-crop failed for input "%s", '
                                 'proceeding with no crop. error: %s',
                                 name, ex.output)
                return '0:0:0:0'

        crops = re.findall(crop_re, out)
        if not crops:
            self.logger.info('No crop found for input "%s", '
                             'proceeding with no crop', name)

            return '0:0:0:0'
        else:
            # use the smallest crop for each edge. prefer non-zero values if
            # they exist
            dimensions = zip(*[map(int, c.split(':')) for c in crops])
            crop = ':'.join(map(str, [non_zero_min(piece) for piece in dimensions]))
            self.logger.info('Using crop "%s" for input "%s"', crop, name)
            return crop

    def transcode(self, path, crop, meta, interlace):
        name = os.path.basename(path)
        output_name = os.path.splitext(name)[0] + self.get_ext()
        output = os.path.join(self.WORK_DIRECTORY, output_name)
        # if these paths exist in the work directory, remove them first
        for workpath in (output, output + '.log'):
            if os.path.exists(workpath):
                self.logger.info('Removing old work output: "%s"', workpath)
                os.unlink(workpath)

        command_parts = [
            'transcode-video',
            '%s' % interlace,
            '--crop %s' % crop,
            self.parse_audio_tracks(meta),
            self.transcoder_load_config(),
            '--output "%s"' % output,
            '"%s"' % path
        ]
        command = ' '.join(command_parts)
        self.logger.info('Transcoding input "%s" with command: %s',
                         path, command)
        try:
            self.execute(command)
        except subprocess.CalledProcessError as ex:
            self.logger.info('Transcoding failed for input "%s": %s',
                             name, ex.output)
            return None
        self.logger.info('Transcoding completed for input "%s"', name)
        return output

    def get_ext(self):
        "Set the output file extension"
        config = configparser.ConfigParser()
        config.read(self.CONFIG_FILE)
        str = ''
        if config.has_option('OUTPUT', 'FileFormat'):
            if config['OUTPUT']['FileFormat'] in ['mp4', 'm4v']:
               return '.' + config['OUTPUT']['FileFormat']

        return '.mkv'

    def transcoder_load_config(self):
        "Load the configuration file"
        config = configparser.ConfigParser()
        config.read(self.CONFIG_FILE)


        DIRECT_OPTIONS = ['VIDEO', 'AUDIO', 'SUBTITLES']
        TOGGLE_OPTIONS = ['TOGGLES']
        COMPRESSED_OPTIONS = ['ADVANCED-ENCODER', 'ADVANCED-HANDBRAKE']

        str = ''

        for sec in config.sections():
            if sec in DIRECT_OPTIONS:
               for key in config[sec]:
                   if config[sec][key] != '':
                      str = str + ' --' + key + ' ' + config[sec][key]
            elif sec in TOGGLE_OPTIONS:
                 for key in config[sec]:
                     if config[sec][key] != '':
                        if config[sec][key] == 'on':
                           str = str + ' --' + key
            elif sec in COMPRESSED_OPTIONS:
                 for key in config[sec]:
                     if config[sec][key] != '':
                        if sec == 'ADVANCED-HANDBRAKE':
                           opt_mod = ' -H '
                        else:
                           opt_mod = ' -E '

                     str = str + opt_mod + config[sec][key]
            else:
                if sec == 'OUTPUT':
                   for key in config[sec]:
                       if config[sec][key] in ['mp4', 'm4b']:
                          str = str + ' --' + config[sec][key]
                if sec == 'QUALITY':
                   for key in config[sec]:
                       if key == 'bitrate':
                          str = str + ' --' + config[sec][key]
                       if key == 'target':
                          str = str + ' --target ' + config[sec][key]
                       if key == 'speed':
                          str = str + ' --' + config[sec][key]
                       if key == 'preset':
                          str = str + ' --preset ' + config[sec][key]

        return ' ' + str + ' '

    def parse_audio_tracks(self, meta):
        "Parse the meta info for audio tracks beyond the first one"

        # find all the audio streams and their optional language and title data
        streams = []
        stream_re = r'(\s{4}Stream #[0-9]+\.[0-9]+(?:\((?P<lang>[a-z]+)\))?: Audio:.*?\n)(?=(?:\s{4}Stream)|(?:[^\s]))'
        title_re = r'^\s{6}title\s+:\s(?P<title>[^\n]+)'
        for stream, lang in re.findall(stream_re, meta, re.DOTALL | re.MULTILINE):
            lang = lang = ''
            title = ''
            title_match = re.search(title_re, stream, re.MULTILINE)
            if title_match:
                title = title_match.group(1)
            streams.append({'title': title, 'lang': lang})

        # find the audio track numbers
        tracks = []
        pos = meta.find('+ audio tracks:')
        track_re = r'^\s+\+\s(?P<track>[0-9]+),\s(?P<title>[^\(\n]*)'
        for line in meta[pos:].split('\n')[1:]:
            if line.startswith('  + subtitle tracks:'):
                break
            match = re.match(track_re, line)
            if match:
                tracks.append({'number': match.group(1), 'title': match.group(2)})

        # assuming there's an equal number of tracks and streams, we can
        # match up stream titles to tracks and have a nicer output
        use_stream_titles = len(streams) == len(tracks)
        additional_tracks = []

        for i, track in enumerate(tracks[1:]):
            title = ''
            if use_stream_titles:
                title = streams[i+1]['title']
            title = title or track['title']
            # remove any quotes in the title so we don't mess up the command
            title = title.replace('"', '')
            self.logger.info('Adding audio track #%s with title: %s',
                             track['number'], title)
            additional_tracks.append('--add-audio %s="%s"' % (
                track['number'], title.replace('"', '')))

        return ' '.join(additional_tracks)


if __name__ == '__main__':
    transcoder = Transcoder()
    transcoder.run()
