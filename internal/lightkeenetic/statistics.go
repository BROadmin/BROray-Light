package lightkeenetic

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
	"strings"
)

var (
	statisticsModel  = regexp.MustCompile(`^(KN|NC)-[0-9]{4}$`)
	statisticsSerial = regexp.MustCompile(`^[A-Z0-9][A-Z0-9-]{5,47}$`)
)

// InstallationStatisticsIdentity returns optional model and device key fields.
// The serial remains local to this call.
func (c *Client) InstallationStatisticsIdentity(ctx context.Context) (model, deviceKey string) {
	if reply, err := c.run(ctx, "show version"); err == nil {
		version := fields(reply)
		model = statisticsModelCode(version["hw_id"])
		if model == "" {
			model = statisticsModelCode(version["model"])
		}
	}
	if reply, err := c.run(ctx, "show identification"); err == nil {
		serial := strings.ToUpper(strings.TrimSpace(fields(reply)["serial"]))
		if statisticsSerial.MatchString(serial) {
			sum := sha256.Sum256([]byte("broray-light-router-key-v1\x00" + serial))
			deviceKey = hex.EncodeToString(sum[:])
		}
	}
	return model, deviceKey
}

func statisticsModelCode(value string) string {
	value = strings.ToUpper(strings.TrimSpace(value))
	if statisticsModel.MatchString(value) {
		return value
	}
	suffix, found := strings.CutSuffix(value, ")")
	index := strings.LastIndexByte(suffix, '(')
	if found && index >= 0 && statisticsModel.MatchString(suffix[index+1:]) {
		return suffix[index+1:]
	}
	return ""
}
