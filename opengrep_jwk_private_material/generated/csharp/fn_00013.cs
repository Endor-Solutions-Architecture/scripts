using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"Qysj3yDNMwmx","alg":"RS256","n":"F2P1omhOup-UxGstwPWTYXddKXCwfp9nVj4KSUkDi3gkZzef","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"Qysj3yDNMwmx\",\"alg\":\"RS256\",\"n\":\"F2P1omhOup-UxGstwPWTYXddKXCwfp9nVj4KSUkDi3gkZzef\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
