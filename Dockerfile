FROM phusion/baseimage:jammy-1.0.1 AS ffmpeg
#FROM phusion/baseimage:master

RUN apt-config dump | grep -we Recommends -e Suggests | sed s/1/0/ | tee /etc/apt/apt.conf.d/999norecommend

RUN apt-get update && apt-get install -y
RUN apt-get install -y build-essential
RUN apt-get install -y crudini
RUN apt-get install -y dnsutils
RUN apt-get install -y fdkaac
RUN apt-get install -y gcc
RUN apt-get install -y git
RUN apt-get install -y git-core
RUN apt-get install -y iputils-ping
RUN apt-get install -y libfdk-aac-dev
RUN apt-get install -y libmp3lame-dev
RUN apt-get install -y texinfo
RUN apt-get install -y wget

#Build layer
RUN echo "---- INSTALL BUILD-DEPENDENCIES ----" && \
    buildDeps='gcc \
    g++ \
    make \
    autoconf \
    automake \
    build-essential \
    cmake \
    git-core \
    libass-dev \
    libfreetype6-dev \
    libgnutls28-dev \
    libmp3lame-dev \
    libsdl2-dev \
    libtool \
    libva-dev \
    libvdpau-dev \
    libvorbis-dev \
    libxcb1-dev \
    libxcb-shm0-dev \
    libxcb-xfixes0-dev \
    meson \
    ninja-build \
    pkg-config \
    texinfo \
    yasm \
    libfdk-aac-dev \
    zlib1g-dev' && \
    set -x && \
    apt-get update && apt-get install -y $buildDeps --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    echo "---- BUILD & INSTALL MP4V2 ----" && \
    mkdir -p /tmp && \
    cd /tmp && \
    git clone https://github.com/sandreas/mp4v2 && \
    cd mp4v2 && \
    ./configure && \
    make && \
    make install && \
    make distclean && \
    echo "---- BUILD & INSTALL ffmpeg ----" && \
    mkdir -p ~/ffmpeg_sources ~/bin && \
    cd ~/ffmpeg_sources && \
    git -C fdk-aac pull 2> /dev/null || git clone --depth 1 https://github.com/mstorsjo/fdk-aac && \
    cd fdk-aac && \
    autoreconf -fiv && \
    ./configure --prefix="$HOME/ffmpeg_build" --disable-shared && \
    make && \
    make install && \
    make distclean && \
    cd ~/ffmpeg_sources && \
    wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
    tar xjvf ffmpeg-snapshot.tar.bz2 && \
    cd ffmpeg && \
    PATH="$HOME/bin:$PATH" PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" ./configure \
    --prefix="$HOME/ffmpeg_build" \
    --pkg-config-flags="--static" \
    --extra-cflags="-I$HOME/ffmpeg_build/include" \
    --extra-ldflags="-L$HOME/ffmpeg_build/lib" \
    --extra-libs="-lpthread -lm" \
    --ld="g++" \
    --bindir="$HOME/bin" \
    --enable-libfdk-aac \
    --enable-nonfree && \
    PATH="$HOME/bin:$PATH" make && \
    make install && \
    hash -r && \
    make distclean && \
    mv ~/bin/* /bin/ && \
    echo "---- REMOVE ALL BUILD-DEPENDENCIES ----" && \
    apt-get purge -y --auto-remove $buildDeps && \
    ldconfig && \
    rm -r /tmp/* ~/ffmpeg_sources ~/bin

FROM ffmpeg AS m4b-tool

#ENV WORKDIR /mnt/
#ENV M4BTOOL_TMP_DIR /tmp/m4b-tool/
LABEL Description="Container to run m4b-tool as a deamon."

RUN echo "---- INSTALL M4B-TOOL DEPENDENCIES ----" && \
    apt-get update && apt-get install -y \
    fdkaac \
    php-cli \
    php-intl \
    php-json \
    php-mbstring \
    php-xml \
    libxcb-shm0-dev \
    libxcb-xfixes0-dev \
    libasound-dev \
    libsdl2-dev \
    libva-dev \
    libvdpau-dev

#Mount volumes
VOLUME /temp
VOLUME /config

#install actual m4b-tool
#RUN echo "---- INSTALL M4B-TOOL ----" && \
#    wget https://github.com/sandreas/m4b-tool/releases/download/v.0.4.2/m4b-tool.phar -O /usr/local/bin/m4b-tool && \
#    chmod +x /usr/local/bin/m4b-tool
ARG M4B_TOOL_DOWNLOAD_LINK="https://github.com/sandreas/m4b-tool/releases/latest/download/m4b-tool.tar.gz"
RUN echo "---- INSTALL M4B-TOOL ----" \
    && if [ ! -f /tmp/m4b-tool.phar ]; then \
    wget "${M4B_TOOL_DOWNLOAD_LINK}" -O /tmp/m4b-tool.tar.gz && \
    if [ ! -f /tmp/m4b-tool.phar ]; then \
    tar xzf /tmp/m4b-tool.tar.gz -C /tmp/ && rm /tmp/m4b-tool.tar.gz ;\
    fi \
    fi \
    && mv /tmp/m4b-tool.phar /usr/local/bin/m4b-tool \
    && M4B_TOOL_PRE_RELEASE_LINK=$(wget -q -O - https://github.com/sandreas/m4b-tool/releases/tag/latest | grep -o 'M4B_TOOL_DOWNLOAD_LINK=[^ ]*' | head -1 | cut -d '=' -f 2) \
    && wget "${M4B_TOOL_PRE_RELEASE_LINK}" -O /tmp/m4b-tool.tar.gz \
    && tar xzf /tmp/m4b-tool.tar.gz -C /tmp/ && rm /tmp/m4b-tool.tar.gz \
    && mv /tmp/m4b-tool.phar /usr/local/bin/m4b-tool-pre \
    && chmod +x /usr/local/bin/m4b-tool /usr/local/bin/m4b-tool-pre

FROM m4b-tool as python

ENV PUID=""
ENV PGID=""
ENV CPU_CORES=""
ENV SLEEPTIME=""

#Python deps
RUN echo "---- INSTALL PYTHON & DEPENDENCIES ----"
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get install -y python3.12
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1
# add python dir to path
ENV PATH="/usr/bin/python3.12/bin:${PATH}"
# check we are running python3.12, and fail if not (use bash)
RUN echo "---- CHECK PYTHON VERSION ----" && \
    if [ "$(python --version | cut -d ' ' -f 2 | cut -d '.' -f 1-2)" != "3.12" ]; then \
    echo "Python 3.12 is required, but you are running $(python --version | cut -d ' ' -f 2)" && \
    exit 1; \
    fi

# install pip from get-pip.py
RUN echo "---- INSTALL PIP ----" && \
    wget https://bootstrap.pypa.io/get-pip.py && \
    python get-pip.py && \
    rm get-pip.py
# RUN apt-get install -y ffmpeg
RUN pip install setuptools wheel
RUN pip install --no-cache-dir --upgrade pip
RUN pip install pipenv

RUN echo "---- INSTALL AUTO-M4B & DEPENDENCIES ----"

RUN mkdir -p /etc/service/bot
ADD runscript.sh /etc/service/bot/run
# ADD auto-m4b-tool.sh /

# copy Pipfile and Pipfile.lock to /auto-m4b
RUN mkdir -p /auto-m4b
ADD Pipfile /auto-m4b/
ADD Pipfile.lock /auto-m4b/
ADD pyproject.toml /auto-m4b/
ADD src /auto-m4b/src

# Copy my_init because built-in one is broken in later python versions
ADD my_init_py312.py /usr/sbin/my_init

#use the remommended clean command
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Remove obnoxious cron php session cleaning
RUN rm -f /etc/cron.d/php
RUN systemctl stop phpsessionclean.service &> /dev/null
RUN systemctl disable phpsessionclean.service &> /dev/null
RUN systemctl stop phpsessionclean.timer &> /dev/null
RUN systemctl disable phpsessionclean.timer &> /dev/null

# append `EXTRA_OPTS="-L 0"` to /etc/default/cron
RUN echo 'EXTRA_OPTS="-L 0"' >> /etc/default/cron

# replace the line that starts with `filter f_syslog3` in /etc/syslog-ng/syslog-ng.conf with `filter f_syslog3 { not facility(cron, auth, authpriv, mail) and not filter(f_debug); };`
RUN sed -i 's/^filter f_syslog3.*/filter f_syslog3 { not facility(cron, auth, authpriv, mail) and not filter(f_debug); };/' /etc/syslog-ng/syslog-ng.conf

# install zsh and omz and set it as default shell
RUN apt-get update && apt-get install -y zsh
RUN sh -c "$(wget -O- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended
RUN sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd
RUN chsh -s /usr/bin/zsh
