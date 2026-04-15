package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"mSRQitG0hDPI","alg":"RS256","n":"DDpiFekhd3vOgUXbaLAfKbFgxD8wl-6Fh2Jawyp24NT5EsWt","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"mSRQitG0hDPI","alg":"RS256","n":"DDpiFekhd3vOgUXbaLAfKbFgxD8wl-6Fh2Jawyp24NT5EsWt","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
