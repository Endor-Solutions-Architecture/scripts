using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"HxAnx0UCkeDd","alg":"RS256","n":"_X_JsYEq7w9UnzZavfTwVgnxzwMpMmP8s4hWxsayGOjQeFkh","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"HxAnx0UCkeDd\",\"alg\":\"RS256\",\"n\":\"_X_JsYEq7w9UnzZavfTwVgnxzwMpMmP8s4hWxsayGOjQeFkh\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
