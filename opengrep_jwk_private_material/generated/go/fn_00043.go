package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"EGhF4hPEkOa_","alg":"RS256","n":"SuDTvt0vavIgepNWnXDRDpQ8ePay_UgBU_FiaNkwXvdk8iaz","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"EGhF4hPEkOa_","alg":"RS256","n":"SuDTvt0vavIgepNWnXDRDpQ8ePay_UgBU_FiaNkwXvdk8iaz","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
