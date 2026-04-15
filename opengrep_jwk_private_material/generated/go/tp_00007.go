package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"oct","kid":"oDQims2TNb9J","alg":"HS256","k":"87dPLCZu_xhGRBM0VqPpDoWWiSGpBJwu-CBNtgMIyneY6oBMxw9-yCUw_X1Yr-rC"}
func main() {
  m := map[string]any{"kty":"oct","kid":"oDQims2TNb9J","alg":"HS256","k":"87dPLCZu_xhGRBM0VqPpDoWWiSGpBJwu-CBNtgMIyneY6oBMxw9-yCUw_X1Yr-rC"}
  _ = jwt.MapClaims{"jwk": m}
}
