package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"4XZeZacznYqU","alg":"RS256","n":"VtnyvTMtxzytRZPVz7M1XtzZnLtjE00PnNCrMhrvv3_54qff","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"4XZeZacznYqU","alg":"RS256","n":"VtnyvTMtxzytRZPVz7M1XtzZnLtjE00PnNCrMhrvv3_54qff","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
