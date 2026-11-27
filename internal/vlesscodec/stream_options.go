package vlesscodec

import (
	"encoding/json"
	"strings"

	"github.com/BROadmin/broray-light/internal/strictjson"
)

// StreamOptions carries only explicitly supported client-side stream fields.
// It cannot change listeners, routing, ownership, or process configuration.
func streamOptionsError(r Record) *ParseError {
	if !has(r, "streamOptions") {
		return nil
	}
	m, ok := r["streamOptions"].(map[string]any)
	if !ok {
		return die("streamOptions должен быть объектом")
	}
	b, e := json.Marshal(m)
	if e != nil || len(b) > 8192 {
		return die("streamOptions превышает допустимый размер")
	}
	bad := func(k string) *ParseError {
		return die("неподдерживаемое или неправильное поле streamOptions: " + safeField(k))
	}
	for block, v := range m {
		opts, ok := v.(map[string]any)
		if !ok {
			return bad(block)
		}
		expected := map[string]string{"wsSettings": "ws", "httpupgradeSettings": "httpupgrade", "grpcSettings": "grpc"}
		if block != "sockopt" && (expected[block] == "" || expected[block] != r["network"]) {
			return bad(block)
		}
		if block == "sockopt" {
			// The same pinned client socket schema is used at the stream root
			// and inside FinalMask TLS. Do not silently narrow signed values,
			// Happy Eyeballs options, or the case-insensitive core enums here.
			if e := freshSocket(opts, "streamOptions.sockopt", 0); e != nil {
				return e
			}
			continue
		}
		for k, val := range opts {
			valid := false
			switch block {
			case "wsSettings", "httpupgradeSettings":
				switch k {
				case "headers":
					headers, ok := val.(map[string]any)
					valid = ok && len(headers) <= 32
					seen := map[string]bool{}
					for name, value := range headers {
						lower := strings.ToLower(name)
						if !headerToken(name) || lower == "host" || seen[lower] || !textValue(value) {
							valid = false
							break
						}
						seen[lower] = true
					}
				case "heartbeatPeriod":
					_, valid = freshUnsigned(val, 32)
					valid = block == "wsSettings" && valid
				}
			case "grpcSettings":
				switch k {
				case "idle_timeout", "health_check_timeout", "initial_windows_size":
					_, valid = freshSigned(val, 32)
				case "permit_without_stream":
					_, valid = val.(bool)
				case "user_agent":
					valid = textValue(val)
				}
			}
			if !valid {
				return bad(block + "." + k)
			}
		}
	}
	return nil
}

func safeField(s string) string {
	if len(s) > 96 {
		return "(имя поля скрыто)"
	}
	for _, c := range s {
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || strings.ContainsRune("._-", c)) {
			return "(имя поля скрыто)"
		}
	}
	return s
}

func headerToken(s string) bool {
	if len(s) == 0 || len(s) > 128 {
		return false
	}
	for _, c := range s {
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || strings.ContainsRune("!#$%&'*+-.^_`|~", c)) {
			return false
		}
	}
	return true
}

func parseLink(link, id string, source map[string]any) (Record, *ParseError) {
	p, err := parseVless(link)
	if err != nil {
		return nil, err
	}
	r, err := saveVless(link, id, source, p)
	if err != nil {
		return nil, err
	}
	// Check the original JSON as well as the normalized legacy result.
	body, _, _ := splitFirst(link, '#')
	_, raw, _ := splitFirst(body, '?')
	q := query(raw)
	for _, field := range []string{"extra", "header", "fm", "streamOptions"} {
		if !q.has(field) {
			continue
		}
		v, err := q.value(field)
		if err != nil {
			return nil, err
		}
		if v == "" {
			continue
		}
		if _, err := strictjson.Decode([]byte(v)); err != nil {
			return nil, die("неправильный или неоднозначный JSON: " + field)
		}
	}
	if err := auditQuery(q, r); err != nil {
		return nil, err
	}
	if err := validateQueryContext(q, r); err != nil {
		return nil, err
	}
	if q.has("streamOptions") {
		s, e := q.value("streamOptions")
		if e != nil {
			return nil, e
		}
		if len(s) > 8192 {
			return nil, die("streamOptions превышает допустимый размер")
		}
		v, ok := decodeJSON(s)
		if !ok || !isObject(v) {
			return nil, die("неправильный JSON streamOptions")
		}
		r["streamOptions"] = v
		if e := streamOptionsError(r); e != nil {
			return nil, e
		}
	}
	if e := validate(r, tempLabel()); e != nil {
		return nil, e
	}
	if e := validateFreshFinalMasks(r); e != nil {
		return nil, e
	}
	return r, nil
}

const mlkemMetadataWarning = "support-x25519mlkem768 предназначен для Mihomo. В Xray использование X25519MLKEM768 определяется TLS-профилем и сервером; этот флаг отдельно не применяется."

func auditQuery(q query, r Record) *ParseError {
	allowed := []string{"streamOptions", "type", "security", "encryption", "flow", "sni", "fp", "pbk", "sid", "spx", "host", "authority", "path", "serviceName", "service_name", "mode", "headerType", "extra", "alpn", "allowInsecure", "insecure", "header", "ech", "pcs", "vcn", "pqv", "fm", "seed", "mtu", "tti", "uplinkCapacity", "downlinkCapacity", "cwndMultiplier", "maxSendingWindow"}
	if q.has("extra") && r["network"] != "xhttp" {
		raw, _ := q.value("extra")
		if raw != "" && raw != "{}" {
			return die("поле extra поддерживается только для XHTTP")
		}
	}
	if q.has("x_padding_bytes") {
		if r["network"] != "xhttp" {
			return die("поле x_padding_bytes поддерживается только для XHTTP")
		}
		padding, _ := q.value("x_padding_bytes")
		if _, ok := rangePair(padding); !ok {
			return die("неправильное поле x_padding_bytes")
		}
		for _, block := range []string{"transport", "xhttp"} {
			m, ok := r[block].(map[string]any)
			if !ok {
				continue
			}
			extra, ok := m["extra"].(map[string]any)
			if !ok {
				extra = map[string]any{}
				m["extra"] = extra
			}
			if old, exists := extra["xPaddingBytes"]; exists && !jsonValueEqual(old, padding) {
				return die("конфликт x_padding_bytes и extra.xPaddingBytes")
			}
			extra["xPaddingBytes"] = padding
		}
	}
	allowed = append(allowed, "x_padding_bytes")
	metadata := []string{"support-x25519mlkem768"}
	allowed = append(allowed, metadata...)
	if e := queryKeys(q, allowed...); e != nil {
		return e
	}
	var warnings []any
	for _, key := range metadata {
		if q.has(key) {
			warnings = append(warnings, mlkemMetadataWarning)
		}
	}
	if len(warnings) > 0 {
		r["importWarnings"] = warnings
	}
	return nil
}

func mergeStreamOptions(st map[string]any, r Record) {
	m, _ := r["streamOptions"].(map[string]any)
	for block, v := range m {
		target, _ := st[block].(map[string]any)
		if target == nil {
			target = map[string]any{}
			st[block] = target
		}
		opts, _ := v.(map[string]any)
		for k, val := range opts {
			target[k] = val
		}
	}
}

func queryKeys(q query, allowed ...string) *ParseError {
	for _, item := range q.items() {
		key, err := uriDecode(itemKey(item))
		if err != nil {
			return err
		}
		if !in(key, allowed...) {
			// The value may contain credentials. Even a field name is bounded
			// and checked before including it in a public error.
			if len(key) > 64 || !isText(key) {
				return die("неподдерживаемое поле URI")
			}
			return die("неподдерживаемое поле URI: " + safeField(key))
		}
		if _, err := q.value(key); err != nil {
			return err
		}
	}
	return nil
}

// ValidateStreamOptions is shared by URI, stored records and Xray JSON import.
func ValidateStreamOptions(network string, options map[string]any) error {
	if e := streamOptionsError(Record{"network": network, "streamOptions": options}); e != nil {
		return e
	}
	return nil
}
