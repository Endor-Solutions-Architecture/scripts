package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"GyqRehG1Nbfo","alg":"RS256","n":"4O7j-so0gC5j4vnleYHmAHgzO9gl3f7UaXE0nKZtdRz0zYMw","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"GyqRehG1Nbfo","alg":"RS256","n":"4O7j-so0gC5j4vnleYHmAHgzO9gl3f7UaXE0nKZtdRz0zYMw","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
