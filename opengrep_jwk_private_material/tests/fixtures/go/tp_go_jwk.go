package main; import "github.com/golang-jwt/jwt/v5"; func main() { jwk := map[string]any{"kty":"RSA","d":"privateExponentValueForFixture","n":"modulus","e":"AQAB"}; _ = jwt.MapClaims{"jwk": jwk} }
