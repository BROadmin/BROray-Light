package servers

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/BROadmin/broray-light/internal/vlesscodec"
)

func parseVLESS(link string) (Server, error) {
	const scheme = "vless://"
	record, stream, err := vlesscodec.Parse(scheme + link[len(scheme):])
	if err != nil {
		return Server{}, fmt.Errorf("%w: %v", ErrInvalid, err)
	}
	data, err := json.Marshal(record)
	if err != nil {
		return Server{}, ErrInvalid
	}
	var s Server
	if err := json.Unmarshal(data, &s); err != nil {
		return Server{}, ErrInvalid
	}
	// The parser's temporary ID is only used for donor record validation.
	s.ID = ""
	s.URI = link
	s.Source = Source{}
	exact, err := json.Marshal(stream)
	if err != nil {
		return Server{}, ErrInvalid
	}
	base, err := json.Marshal(streamSettings(s))
	if err != nil {
		return Server{}, ErrInvalid
	}
	if !bytes.Equal(exact, base) {
		s.VLESSStream = exact
	}
	return s, nil
}

func vlessStreamSettings(s Server) map[string]any {
	decoder := json.NewDecoder(bytes.NewReader(s.VLESSStream))
	decoder.UseNumber()
	var stream map[string]any
	if err := decoder.Decode(&stream); err != nil || stream == nil {
		return nil
	}
	// Light's subscription rotation comparison clears these fields on a copy.
	// Preserve the rest of the validated settings, including nested values.
	if tls, ok := stream["tlsSettings"].(map[string]any); ok && s.TLS.ServerName == "" {
		delete(tls, "serverName")
	}
	if reality, ok := stream["realitySettings"].(map[string]any); ok {
		if s.Reality.ServerName == "" {
			delete(reality, "serverName")
		}
		if s.Reality.ShortID == "" {
			delete(reality, "shortId")
		}
	}
	return stream
}
