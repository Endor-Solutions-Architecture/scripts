package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"9UlQz0JsQavY","alg":"RS256","n":"JEgK1Z6mBkM8yQAsbHAwiA9CM8pfvRNwCvEfMA9VNcYzk9af","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"9UlQz0JsQavY","alg":"RS256","n":"JEgK1Z6mBkM8yQAsbHAwiA9CM8pfvRNwCvEfMA9VNcYzk9af","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
