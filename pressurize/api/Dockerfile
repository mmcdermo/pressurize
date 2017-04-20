FROM golang:1.7.5

COPY ./ /go/src/app
RUN cd /go/src/app && go get ./
RUN cd /go/src/app && go build
RUN cd /go/src/app && ls

EXPOSE 5000
WORKDIR /go/src/app/
ENTRYPOINT /go/src/app/app