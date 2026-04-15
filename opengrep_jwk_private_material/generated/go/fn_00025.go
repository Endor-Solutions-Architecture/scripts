package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"kBmwVBGuCob7","alg":"RS256","n":"CajhQG8byoVd6tzwa1OenLAK2XYUvCHLQVi_0EfC8OuC8vMH","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"kBmwVBGuCob7","alg":"RS256","n":"CajhQG8byoVd6tzwa1OenLAK2XYUvCHLQVi_0EfC8OuC8vMH","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
