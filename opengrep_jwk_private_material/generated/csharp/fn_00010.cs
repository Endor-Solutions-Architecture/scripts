using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"h7_8vru98XUd","alg":"RS256","n":"9MU80jrZZKEZrZvfMwm9hu9rCnL4lwLBdg2tJB4mJzFQaFpw","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"h7_8vru98XUd\",\"alg\":\"RS256\",\"n\":\"9MU80jrZZKEZrZvfMwm9hu9rCnL4lwLBdg2tJB4mJzFQaFpw\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
