package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"E7WFt9MWQh5G","alg":"RS256","n":"YJfuR7Izyui4K3Cgc7fIiUswJhDb9CiBIk-ZbNwI4G8Mg_Tp","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"E7WFt9MWQh5G","alg":"RS256","n":"YJfuR7Izyui4K3Cgc7fIiUswJhDb9CiBIk-ZbNwI4G8Mg_Tp","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
