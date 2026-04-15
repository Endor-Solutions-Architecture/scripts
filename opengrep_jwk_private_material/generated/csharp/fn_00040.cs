using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"irX79kcoicWq","alg":"RS256","n":"thUXtbEAbXQfdredNOyGaOW3Mp7NivB4CNlIW7oU3CrK7-Ao","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"irX79kcoicWq\",\"alg\":\"RS256\",\"n\":\"thUXtbEAbXQfdredNOyGaOW3Mp7NivB4CNlIW7oU3CrK7-Ao\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
