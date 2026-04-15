package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"yR6wg9hbWT7S","alg":"RS256","n":"QSq-wrQ3_uzvTsT0WW9lDg8ycyxB03XkJVTaQNnKAIEiU5px","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"yR6wg9hbWT7S","alg":"RS256","n":"QSq-wrQ3_uzvTsT0WW9lDg8ycyxB03XkJVTaQNnKAIEiU5px","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
