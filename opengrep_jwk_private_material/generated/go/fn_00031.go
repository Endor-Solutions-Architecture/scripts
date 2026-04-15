package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"4-e5QD-blD_9","alg":"RS256","n":"wAvT-uJ-gGeTAapt_v3iofTvHcY6Qw5hKTcv0woX9roKof5i","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"4-e5QD-blD_9","alg":"RS256","n":"wAvT-uJ-gGeTAapt_v3iofTvHcY6Qw5hKTcv0woX9roKof5i","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
