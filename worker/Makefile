VERSION=v1
DOCKERUSER=utsavag

build:
	docker build -f Dockerfile-worker -t kt-search-worker .
push:
	docker tag kt-search-worker $(DOCKERUSER)/kt-search-worker:$(VERSION)
	docker push $(DOCKERUSER)/kt-search-worker:$(VERSION)
	docker tag kt-search-worker $(DOCKERUSER)/kt-search-worker:latest
	docker push $(DOCKERUSER)/kt-search-worker:latest

