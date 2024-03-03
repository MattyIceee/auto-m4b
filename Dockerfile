FROM phusion/baseimage:jammy-1.0.1
#FROM phusion/baseimage:master

#Basic Container
RUN echo "---- INSTALL RUNTIME PACKAGES ----"
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y --no-install-recommends
RUN apt-get install -y python3.12
RUN apt-get install -y python3-pip
RUN apt-get install -y git
# RUN apt-get install -y ffmpeg
RUN apt-get install -y dnsutils
RUN apt-get install -y iputils-ping
RUN apt-get install -y wget
RUN apt-get install -y crudini && rm -rf /var/lib/apt/lists/*

#Python deps
RUN echo "---- INSTALL PYTHON PACKAGES ----" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install pipenv

#Build layer
RUN echo "---- INSTALL ALL BUILD-DEPENDENCIES ----" && \
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

#ENV WORKDIR /mnt/
#ENV M4BTOOL_TMP_DIR /tmp/m4b-tool/
LABEL Description="Container to run m4b-tool as a deamon."

RUN echo "---- INSTALL M4B-TOOL DEPENDENCIES ----" && \
    apt-get update && apt-get install -y --no-install-recommends \
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

ENV PUID=""
ENV PGID=""
ENV CPU_CORES=""
ENV SLEEPTIME=""

ADD runscript.sh /etc/service/bot/run
# ADD auto-m4b-tool.sh /

# copy Pipfile and Pipfile.lock to /auto-m4b
ADD Pipfile /auto-m4b/
ADD Pipfile.lock /auto-m4b/
ADD pyproject.toml /auto-m4b/
ADD src /auto-m4b/src

RUN echo "---- INSTALL AUTO-M4B PY DEPENDENCIES ----" && \
    cd /auto-m4b && \
    pipenv update && \
    pipenv install --system --deploy

# check we are running python3.12, and fail if not
RUN python -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor == 12, raise Exception('Python version is not 3.12')"

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
RUN apt-get update
RUN apt-get install -y zsh
RUN sh -c "$(wget -O- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended
RUN sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd
RUN chsh -s /usr/bin/zsh
