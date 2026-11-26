//go:build !linux

package lightkeenetic

func noAlternateIPv6WAN() bool { return false }
