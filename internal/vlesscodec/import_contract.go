package vlesscodec

// Context checks concern fresh input only. Stored records may contain unused
// historical defaults; reading them must not silently rewrite a connection.
func validateQueryContext(q query, rec Record) *ParseError {
	network, security := asString(rec["network"]), asString(rec["security"])
	for _, key := range []string{"flow", "encryption", "authority", "serviceName", "service_name", "mode", "sni", "fp", "alpn", "pbk", "sid", "spx", "pqv", "ech", "pcs", "vcn", "host", "path"} {
		v, err := q.value(key)
		if err != nil {
			return err
		}
		if v == "" {
			continue
		}
		if !contextFieldAllowed(key, v, network, security, asString(get(rec, "transport", "headerType"))) {
			return die("поле " + key + " неприменимо к выбранным протоколу, транспорту или защите")
		}
	}
	return nil
}

func contextFieldAllowed(key, v, network, security, headerType string) bool {
	if v == "" {
		return true
	}
	switch key {
	case "flow", "encryption":
		return true
	case "authority", "serviceName", "service_name":
		return network == "grpc"
	case "mode":
		// An explicit auto on a transport without modes is a neutral
		// compatibility default. Other values must never disappear.
		return in(network, "grpc", "xhttp") || v == "auto"
	case "sni", "fp":
		return in(security, "tls", "reality")
	case "alpn":
		return security == "tls"
	case "pbk", "sid", "spx", "pqv":
		return security == "reality"
	case "ech", "pcs", "vcn":
		return security == "tls"
	case "host":
		return in(network, "ws", "httpupgrade", "grpc", "xhttp") || network == "raw" && headerType == "http" || network == "kcp" && headerType == "dns"
	case "path":
		return in(network, "ws", "httpupgrade", "xhttp") || network == "raw" && headerType == "http" || v == "/"
	}
	return true
}
