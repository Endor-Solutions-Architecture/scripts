package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"XY5ndJmpV0zX","alg":"RS256","n":"Rmg3AOscdJl7LH79R7qMfug9g5InfNsKJ__t2mLi8D4bIsUz","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"XY5ndJmpV0zX","alg":"RS256","n":"Rmg3AOscdJl7LH79R7qMfug9g5InfNsKJ__t2mLi8D4bIsUz","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
