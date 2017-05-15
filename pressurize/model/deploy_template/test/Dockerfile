FROM python
COPY ./ /var/code/
RUN cd /var/code/ && git clone https://github.com/mmcdermo/pressurize && cd pressurize && pip install -e .
RUN pip install -r /var/code/requirements.txt
EXPOSE 5000
ENTRYPOINT ["python", "/var/code/server.py"]
