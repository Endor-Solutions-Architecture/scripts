package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"oct","kid":"GKG6VOuKD-XA","alg":"HS256","k":"0yopTrHPl8RK6EAHxUIyCknzgTfSy4JGyq2HxAXXxRmmjpRziR_AyOS4R6DB5UUA"}
func main() {
  m := map[string]any{"kty":"oct","kid":"GKG6VOuKD-XA","alg":"HS256","k":"0yopTrHPl8RK6EAHxUIyCknzgTfSy4JGyq2HxAXXxRmmjpRziR_AyOS4R6DB5UUA"}
  _ = jwt.MapClaims{"jwk": m}
}
