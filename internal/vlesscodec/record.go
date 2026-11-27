package vlesscodec

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Record is a 3.x server record (/opt/broray/servers/<id>.json, schemaVersion 2)
// as decoded JSON: objects are map[string]any, numbers json.Number/int/float64.
// The schema is the 3.x one byte-for-byte in field names and value types.
type Record = map[string]any

// LabelDir is the directory shown in the 3.x message
// "сервер имеет неправильную структуру: <dir>/server-import.<pid>.json".
const LabelDir = "/opt/broray/tmp"

func tempLabel() string {
	return filepath.Join(LabelDir, "server-import."+strconv.Itoa(os.Getpid())+".json")
}

// ValidID is broray_server_validate_id's character rule ([a-zA-Z0-9._-]+).
func ValidID(id string) bool {
	if id == "" {
		return false
	}
	for i := 0; i < len(id); i++ {
		c := id[i]
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '.' || c == '_' || c == '-') {
			return false
		}
	}
	return true
}

func validateID(id string) *ParseError {
	if id == "" {
		return die("не указан идентификатор сервера")
	}
	if !ValidID(id) {
		return die("идентификатор сервера содержит недопустимые символы")
	}
	return nil
}

func portCheck(port, prefix string) (any, *ParseError) {
	if !allDigits(port) {
		return nil, die("порт " + prefix + "должен быть числом")
	}
	n, err := strconv.Atoi(port)
	if err != nil || n < 1 || n > 65535 {
		return nil, die("порт " + prefix + "должен находиться в диапазоне 1–65535")
	}
	return int64(n), nil
}

func cloneSource(src map[string]any) map[string]any {
	out := make(map[string]any, len(src))
	for k, v := range src {
		out[k] = v
	}
	return out
}

func base(link, id string, source map[string]any, p *parsed, port any) Record {
	return Record{"schemaVersion": 2, "id": id, "name": p.name, "source": cloneSource(source), "uri": link,
		"protocol": p.protocol, "address": p.address, "port": port}
}

func tlsBlock(p *parsed) map[string]any {
	return map[string]any{"serverName": p.sni, "fingerprint": p.fp, "allowInsecure": false, "alpn": p.alpn}
}

func realityBlock(p *parsed) map[string]any {
	return map[string]any{"serverName": p.sni, "fingerprint": p.fp, "publicKey": p.pbk, "shortId": p.sid, "spiderX": p.spx}
}

func transportBlock(p *parsed, extra any) map[string]any {
	return map[string]any{"host": p.host, "path": p.path, "serviceName": p.serviceName, "mode": p.mode, "headerType": p.headerType, "extra": extra}
}

func saveVless(link, id string, source map[string]any, p *parsed) (Record, *ParseError) {
	if p.uuid == "" {
		return nil, die("парсер не вернул UUID")
	}
	if p.address == "" {
		return nil, die("парсер не вернул адрес")
	}
	port, err := portCheck(p.port, "")
	if err != nil {
		return nil, err
	}
	if !in(p.network, "raw", "ws", "grpc", "httpupgrade", "xhttp", "kcp") {
		return nil, die("неподдерживаемый транспорт VLESS: " + p.network)
	}
	if !in(p.security, "none", "tls", "reality") {
		return nil, die("неподдерживаемая защита VLESS: " + p.security)
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
	if p.security == "reality" {
		if !in(p.network, "raw", "grpc", "xhttp") {
			return nil, die("VLESS REALITY не поддерживает этот транспорт")
		}
		if p.sni == "" {
			return nil, die("для VLESS REALITY не указан SNI")
		}
		if p.pbk == "" {
			return nil, die("для VLESS REALITY не указан public key")
		}
	}
	extra, ok := decodeJSON(p.extra)
	if !ok || !isObject(extra) {
		return nil, die("параметр extra содержит неправильный JSON")
	}
	rec := base(link, id, source, p, port)
	rec["uuid"] = p.uuid
	rec["encryption"] = p.encryption
	if p.flow == "" {
		rec["flow"] = nil
	} else {
		rec["flow"] = p.flow
	}
	rec["network"], rec["security"] = p.network, p.security
	rec["tls"] = tlsBlock(p)
	rec["reality"] = realityBlock(p)
	rec["transport"] = transportBlock(p, extra)
	extra2, _ := decodeJSON(p.extra)
	rec["xhttp"] = map[string]any{"path": p.path, "mode": p.mode, "extra": extra2}
	return finish(rec, p)
}

func finish(rec Record, p *parsed) (Record, *ParseError) {
	const badExt = "неправильные параметры TLS/REALITY/FinalMask"
	sub := func(k string) map[string]any {
		m, ok := rec[k].(map[string]any)
		if !ok {
			m = map[string]any{}
			rec[k] = m
		}
		return m
	}
	pins := strings.Map(func(r rune) rune {
		if r == ':' {
			return -1
		}
		if r >= 'A' && r <= 'F' {
			return r + 32
		}
		return r
	}, p.pcs)
	if p.rawHeader != "" {
		h, ok := decodeJSON(p.rawHeader)
		if !ok {
			return nil, die(badExt)
		}
		sub("transport")["header"] = h
	}
	if rec["network"] == "kcp" {
		t := sub("transport")
		kcp := map[string]any{}
		for k, v := range p.kcp {
			kcp[k] = v
		}
		t["kcp"], t["kcpSeed"], t["kcpLegacy"] = kcp, p.kcpSeed, p.kcpLegacy
	}
	if p.ech != "" {
		sub("tls")["echConfigList"] = p.ech
	}
	if p.vcn != "" {
		sub("tls")["verifyPeerCertByName"] = p.vcn
	}
	if pins != "" {
		t := sub("tls")
		if cur := alt(t["pinnedPeerCertSha256"], pins); !jsonEq(cur, pins) {
			return nil, die(badExt)
		}
		t["pinnedPeerCertSha256"] = pins
	}
	if p.pqv != "" {
		sub("reality")["mldsa65Verify"] = p.pqv
	}
	if p.streamMask != "" && p.streamMask != "{}" {
		m, ok := decodeJSON(p.streamMask)
		if !ok {
			return nil, die(badExt)
		}
		sub("transport")["finalMask"] = m
	}
	rec = normalize(rec)
	if !streamFieldsValid(rec) {
		return nil, die("неподдерживаемые параметры TLS/REALITY/FinalMask")
	}
	if err := validate(rec, tempLabel()); err != nil {
		return nil, err
	}
	return rec, nil
}

// normalize round-trips a record through JSON so that every value has the
// decoded shape (json.Number, []any, map[string]any) the validators and the
// files use.
func normalize(rec Record) Record {
	b, err := Marshal(rec)
	if err != nil {
		return rec
	}
	m, ok := decodeObject(b)
	if !ok {
		return rec
	}
	return m
}
