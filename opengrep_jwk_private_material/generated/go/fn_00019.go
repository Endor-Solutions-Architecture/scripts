package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"PHCxVsXfOKKa","alg":"RS256","n":"SN0ygPkFiRaTZffl5g0imEQ2_mG4Cja0_NAExa4MjEy9BUTA","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"PHCxVsXfOKKa","alg":"RS256","n":"SN0ygPkFiRaTZffl5g0imEQ2_mG4Cja0_NAExa4MjEy9BUTA","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
