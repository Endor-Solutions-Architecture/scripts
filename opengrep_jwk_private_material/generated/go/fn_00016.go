package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"wDTp7hbTIv68","alg":"RS256","n":"1IvComjkWVGI75LmaZlSFu6amsUI7Hg6sDuPf_uomJbBQFHF","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"wDTp7hbTIv68","alg":"RS256","n":"1IvComjkWVGI75LmaZlSFu6amsUI7Hg6sDuPf_uomJbBQFHF","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
