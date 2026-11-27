package vlesscodec

import (
	"encoding/json"
	"math"
	"strconv"
	"strings"
)

// parsed holds the BRORAY_* shell variables a 3.x parser produced.
type parsed struct {
	protocol                               string
	uuid, address, port, network, security string
	encryption, flow, sni, fp, pbk, sid    string
	spx, host, path, serviceName, mode     string
	headerType, extra, name, alterID       string
	alpn                                   []any
	password, method, auth                 string
	hy2Ports, obfs, obfsPassword           string
	hy2Timeout                             string
	upMbps, downMbps, pin, finalMask       string
	// stream extensions (util.sh:167-187, 279-305)
	rawHeader, ech, pcs, vcn, pqv, streamMask string
	kcp                                       map[string]any
	kcpSeed                                   string
	kcpLegacy                                 bool
}

// jqNumber is jq `tonumber` of a decimal string.
func jqNumber(s string) any {
	if n, err := strconv.ParseInt(s, 10, 64); err == nil {
		return n
	}
	f, _ := strconv.ParseFloat(s, 64)
	return f
}

func allDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// parseKcpOptions is broray_parse_kcp_options.
func parseKcpOptions(q query, p *parsed) *ParseError {
	p.kcp, p.kcpSeed, p.kcpLegacy = map[string]any{}, "", false
	for _, key := range []string{"congestion", "readBufferSize", "writeBufferSize"} {
		if q.has(key) {
			return die("параметр mKCP " + key + " не поддерживается текущим Xray")
		}
	}
	if p.network != "kcp" {
		for _, key := range []string{"seed", "mtu", "tti", "uplinkCapacity", "downlinkCapacity", "cwndMultiplier", "maxSendingWindow"} {
			if q.has(key) {
				return die("параметр " + key + " поддерживается только для mKCP")
			}
		}
		return nil
	}
	seed, err := q.value("seed")
	if err != nil {
		return err
	}
	p.kcpSeed = seed
	if q.has("seed") || q.has("headerType") {
		p.kcpLegacy = true
	}
	for _, key := range []string{"mtu", "tti", "uplinkCapacity", "downlinkCapacity", "cwndMultiplier", "maxSendingWindow"} {
		v, err := q.value(key)
		if err != nil {
			return err
		}
		if v == "" {
			continue
		}
		if !allDigits(v) {
			return die("mKCP: параметр " + key + " должен быть целым числом")
		}
		p.kcp[key] = jqNumber(v)
	}
	return nil
}

// parseStreamExtensions is broray_parse_stream_extensions.
func parseStreamExtensions(q query, p *parsed) *ParseError {
	if err := parseKcpOptions(q, p); err != nil {
		return err
	}
	var err *ParseError
	if p.rawHeader, err = q.value("header"); err != nil {
		return err
	}
	if q.has("header") {
		if p.network != "raw" || p.rawHeader == "" {
			return silent()
		}
		for _, k := range []string{"host", "path", "headerType"} {
			if q.has(k) {
				return die("header нельзя сочетать с host/path/headerType")
			}
		}
	}
	if p.ech, err = q.value("ech"); err != nil {
		return err
	}
	if p.pcs, err = q.value("pcs"); err != nil {
		return err
	}
	if p.vcn, err = q.value("vcn"); err != nil {
		return err
	}
	if p.pqv, err = q.value("pqv"); err != nil {
		return err
	}
	p.streamMask = "{}"
	if p.network != "hysteria" {
		if p.streamMask, err = q.value("fm"); err != nil {
			return err
		}
		if p.streamMask == "" {
			p.streamMask = "{}"
		}
	}
	return nil
}

func splitNonEmpty(s string) []any {
	out := []any{}
	for _, part := range strings.Split(s, ",") {
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

// ---------- VLESS (lib/parser-vless.sh) ----------

func parseVless(uri string) (*parsed, *ParseError) {
	if uri == "" {
		return nil, die("не указана ссылка VLESS")
	}
	if !strings.HasPrefix(uri, "vless://") {
		return nil, die("поддерживаются только ссылки vless://")
	}
	body := strings.TrimPrefix(uri, "vless://")
	body, fragment, _ := splitFirst(body, '#')
	authority, rawQuery, _ := splitFirst(body, '?')
	q := query(rawQuery)
	if i := strings.IndexByte(authority, '/'); i >= 0 {
		if "/"+authority[i+1:] != "/" {
			return nil, die("путь в ссылке VLESS не поддерживается")
		}
		authority = authority[:i]
	}
	encodedID := authority
	if i := strings.LastIndexByte(authority, '@'); i >= 0 {
		encodedID = authority[:i]
	}
	hp := authority
	if i := strings.IndexByte(authority, '@'); i >= 0 {
		hp = authority[i+1:]
	}
	if encodedID == authority {
		return nil, die("не найден UUID")
	}
	p := &parsed{protocol: "vless"}
	var err *ParseError
	if p.uuid, err = uriDecode(encodedID); err != nil {
		return nil, then(err, "неправильное кодирование VLESS ID")
	}
	p.address, p.port = hostPort(hp)
	fields := []struct {
		dst  *string
		key  string
		alts []string
	}{
		{&p.network, "type", nil}, {&p.security, "security", nil}, {&p.encryption, "encryption", nil},
		{&p.flow, "flow", nil}, {&p.sni, "sni", nil}, {&p.fp, "fp", nil}, {&p.pbk, "pbk", nil},
		{&p.sid, "sid", nil}, {&p.spx, "spx", nil}, {&p.host, "host", nil},
	}
	for _, f := range fields {
		if *f.dst, err = q.value(f.key, f.alts...); err != nil {
			return nil, err
		}
	}
	authorityValue, err := q.value("authority")
	if err != nil {
		return nil, err
	}
	if p.path, err = q.value("path"); err != nil {
		return nil, err
	}
	if p.serviceName, err = q.value("serviceName", "service_name"); err != nil {
		return nil, err
	}
	if p.mode, err = q.value("mode"); err != nil {
		return nil, err
	}
	if p.headerType, err = q.value("headerType"); err != nil {
		return nil, err
	}
	if p.extra, err = q.value("extra"); err != nil {
		return nil, err
	}
	if p.name, err = uriDecode(fragment); err != nil {
		return nil, err
	}
	alpnValue, err := q.value("alpn")
	if err != nil {
		return nil, err
	}
	p.alpn = splitNonEmpty(alpnValue)
	insecure, err := q.value("allowInsecure", "insecure")
	if err != nil {
		return nil, err
	}
	switch insecure {
	case "", "0", "false", "FALSE":
	default:
		return nil, die("неподдерживаемая настройка TLS allowInsecure")
	}
	switch p.network {
	case "", "tcp", "raw":
		p.network = "raw"
	case "ws", "websocket":
		p.network = "ws"
	case "grpc", "kcp":
	case "httpupgrade", "httpUpgrade":
		p.network = "httpupgrade"
	case "xhttp", "splithttp":
		p.network = "xhttp"
	default:
		return nil, die("неподдерживаемый транспорт VLESS: " + p.network)
	}
	switch p.security {
	case "", "none":
		p.security = "none"
	case "tls", "reality":
	default:
		return nil, die("неподдерживаемая защита VLESS: " + p.security)
	}
	if p.network == "grpc" && authorityValue != "" {
		if p.host != "" && p.host != authorityValue {
			return nil, die("VLESS gRPC: host и authority различаются")
		}
		p.host = authorityValue
	}
	if p.security == "reality" && !in(p.network, "raw", "grpc", "xhttp") {
		return nil, die("VLESS REALITY не поддерживает этот транспорт")
	}
	if !in(p.flow, "", "xtls-rprx-vision", "xtls-rprx-vision-udp443") {
		return nil, die("неподдерживаемый режим VLESS flow: " + p.flow)
	}
	if !VlessEncryptionValid(orStr(p.encryption, "none")) {
		return nil, die("неподдерживаемый или некорректный VLESS encryption")
	}
	if p.flow != "" && ((p.network != "raw" && orStr(p.encryption, "none") == "none") || (p.security != "reality" && p.security != "tls")) {
		return nil, die("VLESS Vision требует TLS/REALITY и TCP/RAW либо поддерживаемого VLESS encryption")
	}
	p.fp = orStr(p.fp, "chrome")
	p.path = orStr(p.path, "/")
	if p.network == "grpc" && !in(p.mode, "", "gun", "multi") {
		return nil, die("неподдерживаемый gRPC mode")
	}
	p.mode = orStr(p.mode, "auto")
	p.headerType = orStr(p.headerType, "none")
	p.encryption = orStr(p.encryption, "none")
	p.extra = orStr(p.extra, "{}")
	p.name = orStr(p.name, p.address+":"+p.port)
	if p.security == "tls" && p.sni == "" {
		p.sni = p.address
	}
	if err := parseStreamExtensions(q, p); err != nil {
		return nil, err
	}
	return p, nil
}

func in(s string, set ...string) bool {
	for _, x := range set {
		if s == x {
			return true
		}
	}
	return false
}

func orStr(s, def string) string {
	if s == "" {
		return def
	}
	return s
}

// VlessEncryptionValid is broray_vless_encryption_valid (util.sh:145-164):
// "none" or mlkem768x25519plus.<native|xorpub|random>.<0rtt|1rtt>[.padding…].<keys>.
func VlessEncryptionValid(v string) bool {
	if v == "none" {
		return true
	}
	p := strings.Split(v, ".")
	if len(p) < 4 || p[0] != "mlkem768x25519plus" || !in(p[1], "native", "xorpub", "random") || !in(p[2], "0rtt", "1rtt") {
		return false
	}
	key := -1
	for i := 3; i < len(p); i++ {
		if runeLen(p[i]) >= 20 {
			key = i
			break
		}
	}
	if key < 0 {
		return false
	}
	for _, k := range p[key:] {
		if n := runeLen(k); n != 43 && n != 1579 {
			return false
		}
		for _, r := range k {
			if !(r >= '0' && r <= '9' || r >= 'A' && r <= 'Z' || r >= 'a' && r <= 'z' || r == '-' || r == '_') {
				return false
			}
		}
	}
	padding := p[3:key]
	if len(padding) == 0 {
		return true
	}
	var nums [][3]float64
	for _, pad := range padding {
		if runeLen(pad) >= 20 {
			return false
		}
		parts := strings.Split(pad, "-")
		if len(parts) != 3 {
			return false
		}
		var t [3]float64
		for i, part := range parts {
			if !allDigits(part) {
				return false
			}
			t[i], _ = strconv.ParseFloat(part, 64)
		}
		nums = append(nums, t)
	}
	for _, t := range nums {
		for _, x := range t {
			if x < 0 || x > 2147483647 {
				return false
			}
		}
		if t[1] > t[2] {
			return false
		}
	}
	if nums[0][0] < 100 || nums[0][1] < 35 || nums[0][2] < 35 {
		return false
	}
	sum := 0.0
	for i, t := range nums {
		if i%2 == 0 {
			sum += t[2]
		}
	}
	return sum <= 65553
}

func runeLen(s string) int { return len([]rune(s)) }

func alt(vals ...any) any {
	for i, v := range vals {
		if truthy(v) || i == len(vals)-1 {
			return v
		}
	}
	return nil
}

// truthy is jq truthiness (everything but null and false).
func truthy(v any) bool { return v != nil && v != false }

// jqRaw is `jq -r` output of one value.
func jqRaw(v any) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case string:
		return x
	case bool:
		if x {
			return "true"
		}
		return "false"
	case json.Number:
		return normNumber(string(x))
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case float64:
		return normNumber(strconv.FormatFloat(x, 'g', -1, 64))
	default:
		b, _ := json.MarshalIndent(v, "", "  ")
		return string(b)
	}
}

// jqRawEmpty is `jq -r '… // empty'`.
func jqRawEmpty(v any) string {
	if !truthy(v) {
		return ""
	}
	return jqRaw(v)
}

func normNumber(s string) string {
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return s
	}
	if f == math.Trunc(f) && math.Abs(f) < 1e17 {
		return strconv.FormatInt(int64(f), 10)
	}
	return strconv.FormatFloat(f, 'g', 17, 64)
}

// jqToNumber is jq `tonumber` of a string.
func jqToNumber(s string) (any, bool) {
	t := strings.TrimSpace(s)
	if t == "" {
		return nil, false
	}
	f, err := strconv.ParseFloat(t, 64)
	if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
		return nil, false
	}
	if f == math.Trunc(f) && math.Abs(f) < 9e15 {
		return int64(f), true
	}
	return f, true
}

func compactJSON(v any) string {
	b, err := Marshal(v)
	if err != nil {
		return "null"
	}
	return strings.TrimSuffix(string(b), "\n")
}

func decodeJSON(s string) (any, bool) {
	dec := json.NewDecoder(strings.NewReader(s))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	var extra any
	if dec.Decode(&extra) == nil {
		return nil, false
	}
	return v, true
}

func decodeObject(b []byte) (map[string]any, bool) {
	v, ok := decodeJSON(string(b))
	if !ok {
		return nil, false
	}
	m, ok := v.(map[string]any)
	return m, ok
}

func isObject(v any) bool { _, ok := v.(map[string]any); return ok }

// jsonEq compares a decoded JSON value with a Go literal (numbers by value).
func jsonEq(v any, want any) bool {
	if f, ok := num(v); ok {
		if g, ok := num(want); ok {
			return f == g
		}
		return false
	}
	switch w := want.(type) {
	case string:
		s, ok := v.(string)
		return ok && s == w
	case bool:
		b, ok := v.(bool)
		return ok && b == w
	case nil:
		return v == nil
	}
	return false
}

// num returns a JSON number as float64.
func num(v any) (float64, bool) {
	switch x := v.(type) {
	case json.Number:
		f, err := x.Float64()
		return f, err == nil
	case float64:
		return x, true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	}
	return 0, false
}
