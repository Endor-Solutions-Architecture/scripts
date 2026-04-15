package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"14NxXBC7fzNg","alg":"RS256","n":"AMAG313yW9AHwhAdo-LtBVxaJ0N0u5cPtzemDGKa5MSVEVuV","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"14NxXBC7fzNg","alg":"RS256","n":"AMAG313yW9AHwhAdo-LtBVxaJ0N0u5cPtzemDGKa5MSVEVuV","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
