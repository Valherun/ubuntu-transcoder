# Transcoder Configuration
#
# Everything is Optional, but will effect the file that the transcoder outputs
#   feel free to delete any unused options
#
# Please run the following command inside of your transcoder docker
#   for help in determining what each option does
#     video-transcoding --help
#   You could also visit the Github Repo directly to learn more
#     https://github.com/donmelton/video_transcoding
#
[OUTPUT]
  #FileFormat:


[QUALITY]
  BitRate: avbr
  #Target:
  #Speed:
  #Preset:


[VIDEO]
  #VidEncoder:


[AUDIO]
  main-audio: eng
  add-audio: jpn,spa
  #audio-width:
  #audio-format:
  #keep-ac3-stereo:
  ac3-encoder: eac3
  #ac3-bitrate:
  #pass-ac3-bitrate:
  #copy-audio:
  #copy-audio-name:
  #aac-encoder:


[SUBTITLES]
  burn-subtitle: scan
  #force-subtitle:
  add-subtitle: eng,spa
  #burn-srt:
  #force-srt:
  #bind-srt-language:
  #bind-srt-encoding:
  #bind-srt-offset:


[ADVANCED-ENCODER]
# encoder-option NAME=VALUE|_NAME
#    pass video encoder option by name with value
#    or disable use of option by prefixing name with "_"
#    (e.g.: `vbv-bufsize=8000`)
#    (e.g.: `crf-max`)

# Create a new numbered Option as needed they will be parsed individually
  #encoder-option1: vbv-buffsize=8000
  #encoder-option2: crf-max

[ADVANCED-HANDBRAKE]
# handbrake-option NAME[=VALUE]|_NAME
#     pass `HandBrakeCLI` option by name or by name with value
#         or disable use of option by prefixing name with "_"
#           (e.g.: `-H stop-at=duration:30`)
#           (e.g.: `-H _markers`)
#           (refer to `HandBrakeCLI --help` for more information)
#           (some options are not allowed)
#           (can be used multiple times)

# Create a new numbered Option as needed they will be parsed individually
  #handbrake-option1: stop-at=duration:30
  #handbrake-option2: _markers

[TOGGLES]
  #verbose: on
  #quiet: off
  #reverse-double-order: off
  #no-audio: off
  #no-auto-burn: off



