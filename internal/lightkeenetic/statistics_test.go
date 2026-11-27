package lightkeenetic

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"testing"
	"time"
)

func TestInstallationStatisticsIdentity(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	sum := sha256.Sum256([]byte("broray-light-router-key-v1\x00SYNTHETIC-880179"))
	key := fmt.Sprintf("%x", sum)

	for _, tt := range []struct {
		name, version, identification, model, deviceKey string
	}{
		{"hardware code", "hw_id: kn-2710\nmodel: Keenetic (KN-0001)", "serial: synthetic-880179", "KN-2710", key},
		{"display suffix", "hw_id: other\nmodel: Netcraze (nc-0001)  ", "serial: ab/1234", "NC-0001", ""},
		{"optional replies", "", "serial: synthetic-880179", "", key},
		{"ambiguous fields", "hw_id: KN-2710\nhw_id: KN-0001", "serial: synthetic-880179\nserial: synthetic-880180", "", ""},
		{"trailing display text", "model: Keenetic (KN-2710) external", "", "", ""},
	} {
		t.Run(tt.name, func(t *testing.T) {
			client := &Client{run: func(got context.Context, command string) (string, error) {
				if got != ctx {
					t.Fatal("command did not receive caller context")
				}
				var reply string
				switch command {
				case "show version":
					reply = tt.version
				case "show identification":
					reply = tt.identification
				default:
					t.Fatalf("unexpected command %q", command)
				}
				if reply == "" {
					return "serial: synthetic-880179", errors.New("unavailable")
				}
				return reply, nil
			}}
			model, deviceKey := client.InstallationStatisticsIdentity(ctx)
			if model != tt.model || deviceKey != tt.deviceKey {
				t.Fatalf("model = %q, key matched = %t", model, deviceKey == tt.deviceKey)
			}
		})
	}
}
