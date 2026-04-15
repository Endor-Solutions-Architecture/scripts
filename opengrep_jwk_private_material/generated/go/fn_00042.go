package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"mZrcB_ShF6Hi","alg":"RS256","n":"kPbJrT2uTM2sYqtwChLvoOAtvZDyWn4NYUYmvN67uCe5MV_h","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"mZrcB_ShF6Hi","alg":"RS256","n":"kPbJrT2uTM2sYqtwChLvoOAtvZDyWn4NYUYmvN67uCe5MV_h","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
