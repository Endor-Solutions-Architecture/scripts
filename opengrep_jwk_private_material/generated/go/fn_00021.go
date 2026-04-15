package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"HPw2EzXYKma9","alg":"RS256","n":"QXZwd8KconRXo_X6F8oo6cNqdyahuQHVTSjAXuNtnYFZgre1","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"HPw2EzXYKma9","alg":"RS256","n":"QXZwd8KconRXo_X6F8oo6cNqdyahuQHVTSjAXuNtnYFZgre1","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
