FROM python
COPY ./ /var/code/
RUN for D in `find /var/code/models/ -maxdepth 1 -mindepth 1 -type d`; do pip install -e "${D}"; ls; done;
RUN cd /var/code/ && git clone https://github.com/mmcdermo/pressurize && cd pressurize && pip install -e .
RUN if [ -f /var/code/requirements.txt ]; then pip install -r /var/code/requirements.txt; fi
RUN mkdir /root/.aws/
RUN ls /var/code/
RUN if [ -f /var/code/credentials ]; then cp /var/code/credentials /root/.aws/credentials; echo "Copied creds"; fi
RUN if [ -f /var/code/credentials ]; then cp /var/code/credentials /root/.aws/config; echo "Copied creds"; fi
RUN ls /root/.aws/
RUN ls ~/.aws/
RUN yes | apt-get update
RUN yes | apt-get install ntp
RUN service ntp restart
EXPOSE 5000
ENTRYPOINT ["python", "/var/code/server.py"]
