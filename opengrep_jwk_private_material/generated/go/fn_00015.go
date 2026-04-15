package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"xq8Xcl8FkPWF","alg":"RS256","n":"buLtn9rTgXMAZC0xx83vHQoeoqmQsXxDjVFIgn2fS3syJPKU","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"xq8Xcl8FkPWF","alg":"RS256","n":"buLtn9rTgXMAZC0xx83vHQoeoqmQsXxDjVFIgn2fS3syJPKU","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
