package lightkeenetic

import (
	"context"
	"strconv"
	"strings"
	"time"
)

// WAN reports a recent reliable Keenetic Internet Checker result. Negative
// status also requires confirmation that no independent IPv6 exit remains.
func (c *Client) WAN(ctx context.Context) (known, online bool) {
	reply, err := c.run(ctx, "show internet status")
	if err != nil || ctx.Err() != nil || len(reply) > 32<<10 {
		return false, false
	}
	checked, negative := negativeInternetCheck(reply)
	status := fields(reply)
	positive := status["reliable"] == "yes" && status["internet"] == "yes"
	if positive {
		checked = status["checked"]
	} else if !negative || !noAlternateIPv6WAN() {
		return false, false
	}
	// The checker uses Keenetic's civil clock, which may differ from UTC.
	clock, err := c.run(ctx, "show clock date")
	if err != nil || ctx.Err() != nil {
		return false, false
	}
	now, ok := parseKeeneticClock(clock)
	if !ok || !recentInternetCheck(checked, now) {
		return false, false
	}
	return true, positive
}

func negativeInternetCheck(reply string) (string, bool) {
	if len(reply) > 32<<10 {
		return "", false
	}
	fields := map[string]string{}
	for line := range strings.SplitSeq(reply, "\n") {
		key, value, _ := strings.Cut(strings.TrimSpace(line), ":")
		switch key {
		case "checked", "reliable", "gateway-accessible", "dns-accessible", "host-accessible", "internet":
			if _, duplicate := fields[key]; duplicate {
				return "", false
			}
			fields[key] = strings.TrimSpace(value)
		}
	}
	if fields["reliable"] != "yes" || fields["gateway-accessible"] != "no" || fields["dns-accessible"] != "no" ||
		fields["internet"] != "no" {
		return "", false
	}
	// Some firmware revisions omit this optional Internet Checker field.
	if host, reported := fields["host-accessible"]; reported && host != "no" {
		return "", false
	}
	checked := fields["checked"]
	return checked, checked != ""
}

func recentInternetCheck(stamp string, now time.Time) bool {
	checked, err := time.Parse(time.ANSIC, stamp)
	age := now.Sub(checked)
	return err == nil && age >= 0 && age <= 90*time.Second
}

func parseKeeneticClock(reply string) (time.Time, bool) {
	if len(reply) > 4096 {
		return time.Time{}, false
	}
	parts := make(map[string]int, 6)
	for line := range strings.SplitSeq(reply, "\n") {
		key, value, _ := strings.Cut(strings.TrimSpace(line), ":")
		switch key {
		case "year", "month", "day", "hour", "min", "sec":
			number, err := strconv.Atoi(strings.TrimSpace(value))
			if _, duplicate := parts[key]; err != nil || duplicate {
				return time.Time{}, false
			}
			parts[key] = number
		}
	}
	if len(parts) != 6 || parts["year"] < 1970 || parts["year"] > 9999 {
		return time.Time{}, false
	}
	// Use a common location solely to subtract the two native civil times.
	now := time.Date(parts["year"], time.Month(parts["month"]), parts["day"],
		parts["hour"], parts["min"], parts["sec"], 0, time.UTC)
	year, month, day := now.Date()
	hour, minute, second := now.Clock()
	valid := year == parts["year"] && int(month) == parts["month"] && day == parts["day"] &&
		hour == parts["hour"] && minute == parts["min"] && second == parts["sec"]
	return now, valid
}
