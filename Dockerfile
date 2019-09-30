#transcoder

FROM valherun/ubuntu-media

ARG DEBIAN_FRONTEND="noninteractive"

RUN \
  echo "** Checkout linuxserver.io whom I have shamelessly **" && \
  echo "** Mimicked thier style and used their baseimages in my Dockers **" && \
  apt-get update && \
  echo "** Installing RUBY and python dev pkgs **" && \
  apt-get install -y \
    python-dev \
    python3-dev \
    ruby-full && \
  echo "** Installing pip modules **" && \
  pip install -U setuptools && \
  pip install -U \
    cheetah \
    configparser \
    ndg-httpsclient \
    notify \
    paramiko \
    pillow \
    psutil \
    pyopenssl \
    requests \
    urllib3 \
    virtualenv && \
  echo "** Cleanup **" && \
  apt-get clean && \
  rm -rf \ 
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/* && \
  echo "** Creating Required Directories **" && \
  mkdir -p \
     /transcoder && \
  gem install video_transcoding
  
  COPY root/ /
  
VOLUME /config /transcoder
