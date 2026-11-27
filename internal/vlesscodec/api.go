// Package vlesscodec parses ordinary VLESS share links and renders Xray
// client stream settings.
//
// Derived from BROray v3.5.10, commit
// 92dc010ebad5fd21dff9e625925e9847b3714640. The source is in areas/servers:
// parse.go and uri.go for URI parsing; build.go for the VLESS record;
// import_contract.go, stream_options.go, proxy.go, validate.go, client_fields.go,
// and finalmask_validation*.go for validation; xrayconfig.go for rendering.
// JSON encoding follows internal/compat/json.go. The strict JSON and Xray ID
// helpers retain the donor's internal/strictjson and internal/xrayid packages.
package vlesscodec

import (
	"bytes"
	"encoding/json"
)

// Parse validates a donor-compatible VLESS share link and returns its normalized
// connection record and rendered Xray client stream settings.
func Parse(link string) (record, stream map[string]any, err error) {
	record, parseErr := parseLink(link, "vless", map[string]any{"type": "manual"})
	if parseErr != nil {
		return nil, nil, parseErr
	}
	stream, err = streamSettings(record)
	if err != nil {
		return nil, nil, err
	}
	return record, stream, nil
}

// Marshal encodes without HTML escaping (3.x JSON is produced by jq).
func Marshal(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func nativeError(field string) *ParseError {
	return die("неподдерживаемое или неправильное поле JSON: " + safeField(field))
}
