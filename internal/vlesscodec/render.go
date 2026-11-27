package vlesscodec

import (
	"strings"
)

func compactObject(m map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range m {
		switch x := v.(type) {
		case nil:
			continue
		case string:
			if x == "" {
				continue
			}
		case []any:
			if len(x) == 0 {
				continue
			}
		case map[string]any:
			if len(x) == 0 {
				continue
			}
		}
		out[k] = v
	}
	return out
}

func lenPositive(v any) bool {
	l, ok := jqLength(v)
	return ok && l > 0
}

func tlsSettings(s Record) map[string]any {
	out := compactObject(map[string]any{
		"serverName":           alt(get(s, "tls", "serverName"), get(s, "reality", "serverName"), ""),
		"fingerprint":          alt(get(s, "tls", "fingerprint"), get(s, "reality", "fingerprint"), "chrome"),
		"alpn":                 alt(get(s, "tls", "alpn"), []any{}),
		"echConfigList":        alt(get(s, "tls", "echConfigList"), ""),
		"verifyPeerCertByName": alt(get(s, "tls", "verifyPeerCertByName"), ""),
		"pinnedPeerCertSha256": alt(get(s, "tls", "pinnedPeerCertSha256"), ""),
	})
	for _, field := range clientTLSExtraNames {
		if has(s["tls"], field) {
			out[field] = get(s, "tls", field)
		}
	}
	return out
}

func realitySettings(s Record) map[string]any {
	out := compactObject(map[string]any{
		"serverName":    alt(get(s, "reality", "serverName"), ""),
		"fingerprint":   alt(get(s, "reality", "fingerprint"), "chrome"),
		"publicKey":     alt(get(s, "reality", "publicKey"), ""),
		"shortId":       alt(get(s, "reality", "shortId"), ""),
		"spiderX":       alt(get(s, "reality", "spiderX"), ""),
		"mldsa65Verify": alt(get(s, "reality", "mldsa65Verify"), ""),
	})
	if has(s["reality"], "show") {
		out["show"] = get(s, "reality", "show")
	}
	return out
}

func xhttpSettings(s Record) map[string]any {
	src := "transport"
	if s["protocol"] == "vless" {
		src = "xhttp"
	}
	out := map[string]any{"path": alt(get(s, src, "path"), "/"), "mode": alt(get(s, src, "mode"), "auto")}
	if lenPositive(alt(get(s, "transport", "host"), "")) {
		out["host"] = get(s, "transport", "host")
	}
	if extra := alt(get(s, src, "extra"), map[string]any{}); lenPositive(extra) {
		out["extra"] = extra
	}
	return out
}

func rawSettings(s Record) map[string]any {
	if h := get(s, "transport", "header"); h != nil {
		return map[string]any{"header": h}
	}
	ht := alt(get(s, "transport", "headerType"), "none")
	header := map[string]any{"type": ht}
	if ht == "http" {
		req := map[string]any{"path": []any{alt(get(s, "transport", "path"), "/")}}
		if host := alt(get(s, "transport", "host"), ""); host != "" {
			hs, _ := host.(string)
			parts := []any{}
			for _, p := range strings.Split(hs, ",") {
				parts = append(parts, p)
			}
			req["headers"] = map[string]any{"Host": parts}
		}
		header["request"] = req
	}
	return map[string]any{"header": header}
}

func kcpFinalMask(s Record) any {
	if !truthy(get(s, "transport", "kcpLegacy")) {
		return alt(get(s, "transport", "finalMask"), map[string]any{})
	}
	settings := map[string]any{}
	if seed := alt(get(s, "transport", "kcpSeed"), ""); seed != "" {
		settings["value"] = get(s, "transport", "kcpSeed")
	}
	udp := []any{map[string]any{"type": "mkcp-legacy", "settings": settings}}
	if ht := alt(get(s, "transport", "headerType"), "none"); ht != "none" {
		h := get(s, "transport", "headerType")
		if h == "wechat-video" {
			h = "wechat"
		}
		st := map[string]any{"header": h}
		if get(s, "transport", "headerType") == "dns" && alt(get(s, "transport", "host"), "") != "" {
			st["value"] = get(s, "transport", "host")
		}
		udp = append(udp, map[string]any{"type": "mkcp-legacy", "settings": st})
	}
	return map[string]any{"udp": udp}
}

func streamSettings(s Record) (map[string]any, error) {
	st := map[string]any{"network": s["network"], "security": s["security"]}
	switch s["network"] {
	case "xhttp":
		st["xhttpSettings"] = xhttpSettings(s)
	case "raw":
		st["rawSettings"] = rawSettings(s)
	case "ws":
		ws := map[string]any{"path": alt(get(s, "transport", "path"), "/")}
		if lenPositive(alt(get(s, "transport", "host"), "")) {
			ws["host"] = get(s, "transport", "host")
		}
		st["wsSettings"] = ws
	case "grpc":
		st["grpcSettings"] = compactObject(map[string]any{
			"serviceName": alt(get(s, "transport", "serviceName"), ""),
			"authority":   alt(get(s, "transport", "host"), ""),
			"multiMode":   alt(get(s, "transport", "mode"), "") == "multi",
		})
	case "httpupgrade":
		st["httpupgradeSettings"] = compactObject(map[string]any{
			"path": alt(get(s, "transport", "path"), "/"),
			"host": alt(get(s, "transport", "host"), ""),
		})
	case "kcp":
		st["kcpSettings"] = alt(get(s, "transport", "kcp"), map[string]any{})
	default:
		return nil, die("неподдерживаемый транспорт: " + jqRaw(s["network"]))
	}
	switch s["security"] {
	case "tls":
		st["tlsSettings"] = tlsSettings(s)
	case "reality":
		st["realitySettings"] = realitySettings(s)
	case "none":
	default:
		return nil, die("неподдерживаемая защита: " + jqRaw(s["security"]))
	}
	if s["network"] == "kcp" && lenPositive(kcpFinalMask(s)) {
		st["finalmask"] = kcpFinalMask(s)
	} else if fm := alt(get(s, "transport", "finalMask"), map[string]any{}); lenPositive(fm) {
		st["finalmask"] = get(s, "transport", "finalMask")
	}
	mergeStreamOptions(st, s)
	return st, nil
}
