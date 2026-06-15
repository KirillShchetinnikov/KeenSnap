SHELL := /bin/bash
VERSION := $(shell cat VERSION)
PACKAGE := keensnap
ROOT_DIR := /opt
DEPENDENCIES := curl, tar, ca-certificates, wget-ssl, jq, cron
REPO_OWNER := KirillShchetinnikov
REPO_NAME := KeenSnap
REPO_URL := https://github.com/$(REPO_OWNER)/$(REPO_NAME)
FEED_URL := https://gh.kipik1.ru
PAGES_DOMAIN := gh.kipik1.ru
FEED_ARCHES := aarch64-3.10 armv7-3.2 mips-3.4 mipsel-3.4
IPK_FILE := $(PACKAGE)_$(VERSION)_all.ipk

.PHONY: clean _pkg-clean _pkg-control _pkg-scripts _pkg-ipk keensnap-ipk feed

clean:
	rm -rf out/pkg out/feed

_pkg-clean:
	rm -rf out/$(BUILD_DIR)
	mkdir -p out/$(BUILD_DIR)/control
	mkdir -p out/$(BUILD_DIR)/data

_pkg-control:
	echo "Package: $(PACKAGE)" > out/$(BUILD_DIR)/control/control
	echo "Version: $(VERSION)" >> out/$(BUILD_DIR)/control/control
	echo "Depends: $(DEPENDENCIES)" >> out/$(BUILD_DIR)/control/control
	echo "Section: utils" >> out/$(BUILD_DIR)/control/control
	echo "Architecture: all" >> out/$(BUILD_DIR)/control/control
	echo "License: MIT" >> out/$(BUILD_DIR)/control/control
	echo "URL: $(REPO_URL)" >> out/$(BUILD_DIR)/control/control
	echo "Description: Keenetic backup utility with Telegram and Google Drive support" >> out/$(BUILD_DIR)/control/control

_pkg-scripts:
	cp common/ipk/postinst out/$(BUILD_DIR)/control/postinst
	cp common/ipk/conffiles out/$(BUILD_DIR)/control/conffiles
	cp common/ipk/postrm out/$(BUILD_DIR)/control/postrm
	find out/$(BUILD_DIR)/control -type f -exec sed -i 's/\r$$//' {} +
	chmod +x out/$(BUILD_DIR)/control/postinst
	chmod +x out/$(BUILD_DIR)/control/postrm
	chmod +x out/$(BUILD_DIR)/control/conffiles

_pkg-ipk:
	make _pkg-clean
	make _pkg-control
	make _pkg-scripts
	cd out/$(BUILD_DIR)/control; tar czvf ../control.tar.gz .; cd ../../..

	mkdir -p out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap
	sed 's/^SCRIPT_VERSION=""/SCRIPT_VERSION="$(VERSION)"/' common/keensnap-init > out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap/keensnap-init
	sed 's/^SCRIPT_VERSION=""/SCRIPT_VERSION="$(VERSION)"/' common/keensnap.sh > out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap/keensnap.sh
	cp common/config.conf out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap/config.conf
	find out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap -type f -exec sed -i 's/\r$$//' {} +
	chmod +x out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap/keensnap.sh
	chmod +x out/$(BUILD_DIR)/data$(ROOT_DIR)/root/KeenSnap/keensnap-init
	cd out/$(BUILD_DIR)/data; tar czvf ../data.tar.gz .; cd ../../..

	echo 2.0 > out/$(BUILD_DIR)/debian-binary
	cd out/$(BUILD_DIR); \
	ar r ../$(IPK_FILE) debian-binary control.tar.gz data.tar.gz; \
	cd ../..

keensnap-ipk:
	@make \
		BUILD_DIR=pkg \
		_pkg-ipk

feed: keensnap-ipk
	rm -rf out/feed
	mkdir -p out/feed
	touch out/feed/.nojekyll
	printf '%s\n' "$(PAGES_DOMAIN)" > out/feed/CNAME
	cp add-repo.sh out/feed/add-repo.sh
	cp install.sh out/feed/install.sh
	for arch in $(FEED_ARCHES); do \
		mkdir -p out/feed/$$arch; \
		cp out/$(IPK_FILE) out/feed/$$arch/$(IPK_FILE); \
		{ \
			cat out/pkg/control/control; \
			echo "Filename: $(IPK_FILE)"; \
			echo "Size: $$(wc -c < out/$(IPK_FILE))"; \
			echo "SHA256sum: $$(sha256sum out/$(IPK_FILE) | awk '{print $$1}')"; \
			echo ""; \
		} > out/feed/$$arch/Packages; \
		gzip -9c out/feed/$$arch/Packages > out/feed/$$arch/Packages.gz; \
	done
