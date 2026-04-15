package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"dQm_e7W8l1GW","alg":"RS256","n":"JR88phajKP0FU0mK1hiMuXUhwByG-Ypb6Yr4RmJKGBts68n3","e":"AQAB","d":"mbrHGyp-aNyVOHrhtYq4MwfgEJUS01xbWg5Ar9kTlsewiHxiEIrOsheKPPy75P3i"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"dQm_e7W8l1GW","alg":"RS256","n":"JR88phajKP0FU0mK1hiMuXUhwByG-Ypb6Yr4RmJKGBts68n3","e":"AQAB","d":"mbrHGyp-aNyVOHrhtYq4MwfgEJUS01xbWg5Ar9kTlsewiHxiEIrOsheKPPy75P3i"}
  _ = jwt.MapClaims{"jwk": m}
}
