package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"xexrFNAgZ7at","alg":"RS256","n":"jVPCiZ86QB6dUjoU5Yq_Z0F5DSyovz0sfgySGpZKSBnyCR_r","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"xexrFNAgZ7at","alg":"RS256","n":"jVPCiZ86QB6dUjoU5Yq_Z0F5DSyovz0sfgySGpZKSBnyCR_r","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
