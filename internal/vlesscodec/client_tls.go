package vlesscodec

import (
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"strings"
)

func clientStringList(v any) ([]string, bool) {
	if s, ok := v.(string); ok {
		return strings.Split(s, ","), true
	}
	list, ok := v.([]any)
	if !ok || list == nil {
		return nil, false
	}
	out := make([]string, 0, len(list))
	for _, item := range list {
		s, ok := item.(string)
		if !ok {
			return nil, false
		}
		out = append(out, s)
	}
	return out, true
}

func clientTLSValid(v any, path string) *ParseError {
	m, ok := v.(map[string]any)
	if !ok || m == nil {
		return nativeError(path)
	}
	if b, err := json.Marshal(m); err != nil || len(b) > 262144 {
		return nativeError(path)
	}
	// Reuse the pinned field schema; nested sockopt must follow the same
	// contract as ordinary stream sockopt, including future validated options.
	schema := make(map[string]any, len(m))
	for k, value := range m {
		if k != "echSockopt" {
			schema[k] = value
		}
	}
	if schema["masterKeyLog"] == "none" {
		schema["masterKeyLog"] = ""
	}
	if e := freshTLS(schema, path, 0); e != nil {
		return e
	}
	for _, k := range []string{"serverName", "minVersion", "maxVersion", "cipherSuites", "fingerprint", "pinnedPeerCertSha256", "verifyPeerCertByName", "echConfigList"} {
		if has(m, k) && !textValue(m[k]) {
			return nativeError(path + "." + k)
		}
	}
	versions := map[string]int{"": 0, "1.0": 10, "1.1": 11, "1.2": 12, "1.3": 13}
	min, minOK := versions[asString(m["minVersion"])]
	max, maxOK := versions[asString(m["maxVersion"])]
	if !minOK || !maxOK || min > 0 && max > 0 && min > max {
		return nativeError(path + ".minVersion.maxVersion")
	}
	if suites := asString(m["cipherSuites"]); suites != "" {
		known := map[string]bool{}
		for _, suite := range append(tls.CipherSuites(), tls.InsecureCipherSuites()...) {
			known[suite.Name] = true
		}
		for _, name := range strings.Split(suites, ":") {
			if !known[strings.TrimSpace(name)] {
				return nativeError(path + ".cipherSuites")
			}
		}
	}
	for _, field := range []string{"alpn", "curvePreferences"} {
		if !has(m, field) {
			continue
		}
		list, valid := clientStringList(m[field])
		if !valid || len(list) > 64 {
			return nativeError(path + "." + field)
		}
		for _, item := range list {
			if item == "" || len(item) > 255 || !isText(item) {
				return nativeError(path + "." + field)
			}
			if field == "curvePreferences" && !in(strings.ToLower(item), "curvep256", "curvep384", "curvep521", "x25519", "x25519mlkem768", "secp256r1mlkem768", "secp384r1mlkem1024") {
				return nativeError(path + "." + field)
			}
			if field == "alpn" && strings.EqualFold(item, "frommitm") && len(list) != 1 {
				return nativeError(path + ".alpn")
			}
		}
	}
	if has(m, "echSockopt") {
		opts, ok := m["echSockopt"].(map[string]any)
		if !ok || opts == nil {
			return nativeError(path + ".echSockopt")
		}
		if err := ValidateStreamOptions("raw", map[string]any{"sockopt": opts}); err != nil {
			return nativeError(path + ".echSockopt")
		}
	}
	if has(m, "certificates") {
		certs, ok := m["certificates"].([]any)
		if !ok || certs == nil || len(certs) > 32 {
			return nativeError(path + ".certificates")
		}
		for _, cert := range certs {
			if e := clientTLSCertificate(cert, path+".certificates"); e != nil {
				return e
			}
		}
	}
	return nil
}

func clientTLSCertificate(v any, path string) *ParseError {
	// freshTLSCert above rejects nonempty file paths and validates every type.
	m := v.(map[string]any)
	usage := strings.ToLower(asString(m["usage"]))
	if !in(usage, "", "encipherment", "verify") {
		return nativeError(path + ".usage")
	}
	pemBytes := func(field string) []byte {
		var lines []string
		for _, line := range m[field].([]any) {
			lines = append(lines, line.(string))
		}
		return []byte(strings.Join(lines, "\n"))
	}
	if !has(m, "certificate") {
		return nativeError(path + ".certificate")
	}
	certPEM := pemBytes("certificate")
	remaining := certPEM
	count := 0
	for len(strings.TrimSpace(string(remaining))) > 0 {
		block, rest := pem.Decode(remaining)
		if block == nil || block.Type != "CERTIFICATE" {
			return nativeError(path + ".certificate")
		}
		if _, err := x509.ParseCertificate(block.Bytes); err != nil {
			return nativeError(path + ".certificate")
		}
		count++
		remaining = rest
	}
	if count == 0 {
		return nativeError(path + ".certificate")
	}
	if has(m, "key") && len(m["key"].([]any)) > 0 {
		if _, err := tls.X509KeyPair(certPEM, pemBytes("key")); err != nil {
			return nativeError(path + ".key")
		}
	} else if usage != "verify" {
		return nativeError(path + ".key")
	}
	return nil
}

var clientTLSExtraNames = []string{
	"certificates", "enableSessionResumption", "disableSystemRoot", "minVersion", "maxVersion",
	"cipherSuites", "curvePreferences", "echSockopt", "useSystemCA",
}
