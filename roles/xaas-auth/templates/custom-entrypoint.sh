{# The original /usr/local/bin/entrypoint.sh insists on “pprinting” a frontend.xml file that, in our case, would be empty. #}
#!/bin/bash

. /usr/local/bin/docker-entrypoint.sh

unset -f docker_pprint_metadata

docker_pprint_metadata () {
	# use the SAML2 backend keymat to temporarily sign the generated metadata
	touch backend.xml frontend.xml
	satosa-saml-metadata proxy_conf.yaml backend.key backend.crt
        sed -i 's/ID="id-[^"]*"//' backend.xml

	echo -----BEGIN SAML2 BACKEND METADATA-----
	xq -x 'del(."ns0:EntityDescriptor"."ns1:Signature")' backend.xml | tee backend.xml.new
	echo -----END SAML2 BACKEND METADATA-----

	mv backend.xml.new backend.xml
}

_main gunicorn -b0.0.0.0:8080 epfl.satosa_wsgi:app
