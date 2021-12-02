VERSION=v1
DOCKERUSER=utsavag

build:
	docker build -f Dockerfile-rest -t kt-search-rest .

push:
	docker tag kt-search-rest $(DOCKERUSER)/kt-search-rest:$(VERSION)
	docker push $(DOCKERUSER)/kt-search-rest:$(VERSION)
	docker tag kt-search-rest $(DOCKERUSER)/kt-search-rest:latest
	docker push $(DOCKERUSER)/kt-search-rest:latest
