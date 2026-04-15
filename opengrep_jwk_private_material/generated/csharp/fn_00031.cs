using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"i0IAkCnokgz7","alg":"RS256","n":"Oy17O9DGVpXSW6_H-OBvxDIweiU5acdnbGAj9tJMP8p3h7Hn","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"i0IAkCnokgz7\",\"alg\":\"RS256\",\"n\":\"Oy17O9DGVpXSW6_H-OBvxDIweiU5acdnbGAj9tJMP8p3h7Hn\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
